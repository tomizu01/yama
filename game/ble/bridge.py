"""BLE 通信を専用スレッドで動かして pygame メインループと Queue で繋ぐ。

bleak は asyncio ベースで、pygame ループは普通の同期ループ。両者を混ぜるため
別スレッドで asyncio loop を回し、両方向の Queue でやり取りする
（aicyc-CLAUDE.md と CLAUDE.md フェーズ2方針に従う）。

ゲーム側からは BleBridge のメソッドを呼べばよく、bleak/asyncio を意識する必要はない。
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bleak import BleakClient, BleakScanner

from game.ble import constants as U
from game.ble.parser import (
    CSC_FEATURE_CRANK,
    CSC_FEATURE_WHEEL,
    CPS_FEATURE_CRANK,
    CPS_FEATURE_WHEEL,
    CpsState,
    CscState,
    Telemetry,
)

log = logging.getLogger(__name__)


class DeviceProfile(Enum):
    CSC = "csc"
    CPS = "cps"


@dataclass(frozen=True)
class DeviceCandidate:
    """スキャンで見つかったデバイス1件。"""
    address: str
    name: str
    profiles: tuple[DeviceProfile, ...]   # 公開しているサービス（複数可）
    rssi: int | None = None


@dataclass
class BridgeEvent:
    """BLE スレッド → ゲーム側 への通知。kind と payload で判別する。

    kind:
      "scan_result"  payload: DeviceCandidate           — 検出ごとに1個
      "scan_done"    payload: None                      — スキャン終了
      "connecting"   payload: str (address)
      "connected"    payload: dict — {profile, features (wheel/crank/power), fec}
      "telemetry"    payload: Telemetry
      "disconnected" payload: None
      "reconnecting" payload: str (address) — 自動再接続の試行開始
      "error"        payload: str
    """
    kind: str
    payload: Any = None


# --- コマンド種別（内部用） ---
_CMD_SCAN = "scan"
_CMD_CONNECT = "connect"
_CMD_DISCONNECT = "disconnect"
_CMD_RECONNECT = "reconnect"
_CMD_SET_GRADE = "set_grade"
_CMD_STOP = "stop"

# 自動再接続のリトライ間隔 [s]。デバイスが復帰するまで無限に繰り返す
_RECONNECT_RETRY_S = 3.0

# FE-C Track Resistance (Page 51) の転がり抵抗係数。アスファルト相当
_FEC_CRR = 0.004


def _build_fec_track_resistance(grade_pct: float, crr: float = _FEC_CRR) -> bytes:
    """FE-C Page 51 (Track Resistance) の13バイトメッセージを組み立てる。

    勾配シミュレーション用。docs/tacx-fec-over-ble.md 参照。
    Grade: Uint16 LE, 0.01% 解像度, `(grade% + 200) / 0.01` でエンコード。
    """
    grade_pct = max(-200.0, min(200.0, grade_pct))
    grade_val = round((grade_pct + 200.0) / 0.01)
    msg = bytearray([
        0xA4,                       # Sync
        0x09,                       # Length
        0x4E,                       # Broadcast Data
        0x05,                       # Channel（FE-C over BLE では常に5）
        0x33,                       # Data Page 51
        0xFF, 0xFF, 0xFF, 0xFF,     # Reserved
        grade_val & 0xFF,           # Grade LSB
        (grade_val >> 8) & 0xFF,    # Grade MSB
        round(crr / 0.00005) & 0xFF,  # CRR
    ])
    checksum = 0
    for b in msg:
        checksum ^= b
    msg.append(checksum)
    return bytes(msg)


@dataclass
class _Command:
    kind: str
    args: dict = field(default_factory=dict)


class BleBridge:
    """ゲームスレッドから使う BLE 入口。

    `events` から BridgeEvent を取り出し、必要なメソッドを呼ぶ。
    内部スレッドは1本だけ、close() を呼ぶまで生きている。
    """

    def __init__(self) -> None:
        self.events: queue.Queue[BridgeEvent] = queue.Queue()
        self._cmd: queue.Queue[_Command] = queue.Queue()
        self._loop_ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        # 自動再接続: 確立済み接続が不意に切れたら、このアドレスへ無限リトライする。
        # 意図的な切断（disconnect()/close()/別デバイスへのconnect()）では None に戻す
        self._reconnect_address: str | None = None
        self._reconnect_pending = False   # 再接続コマンドの多重投入防止
        self._expect_disconnect = False   # 意図的切断中は callback で再接続しない
        self._fec_available = False       # 接続中デバイスが FE-C サービスを持つか
        self._thread = threading.Thread(
            target=self._run_thread, name="ble-bridge", daemon=True
        )
        self._thread.start()
        self._loop_ready.wait(timeout=5.0)

    # --- ゲームスレッドから呼ぶ API ---

    def start_scan(self, timeout_s: float = 6.0) -> None:
        self._cmd.put(_Command(_CMD_SCAN, {"timeout": timeout_s}))

    def connect(self, address: str) -> None:
        """指定アドレスに接続。プロファイル（CSC/CPS）は接続後のサービス一覧から自動判定。"""
        self._cmd.put(_Command(_CMD_CONNECT, {"address": address}))

    def disconnect(self) -> None:
        self._cmd.put(_Command(_CMD_DISCONNECT))

    def set_grade(self, grade_pct: float) -> None:
        """FE-C Track Resistance (Page 51) で勾配をトレーナーへ送信する。

        FE-C 非対応デバイス・未接続時は黙って無視される（送信失敗もログのみ）。
        トレーナー側のタイムアウトで負荷が解除される機種があるため、
        呼び出し側（BleSpeedSource）が定期的に再送する前提。
        """
        self._cmd.put(_Command(_CMD_SET_GRADE, {"grade": grade_pct}))

    def request_reconnect(self) -> None:
        """ゲーム側からの強制再接続要求（テレメトリ途絶ウォッチドッグ用）。

        接続済みデバイスから一定時間データが来ない場合の保険。確立済み接続が
        無ければ（_reconnect_address が None）何もしない。
        """
        self._cmd.put(_Command(_CMD_RECONNECT))

    def close(self) -> None:
        self._cmd.put(_Command(_CMD_STOP))
        self._thread.join(timeout=5.0)

    # --- BLE スレッド本体 ---

    def _run_thread(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._loop_ready.set()
        try:
            loop.run_until_complete(self._main())
        except Exception as e:  # 想定外の落下を握りつぶさず通知
            log.exception("BLE bridge thread crashed")
            self.events.put(BridgeEvent("error", f"bridge crashed: {e}"))
        finally:
            loop.close()

    async def _main(self) -> None:
        loop = asyncio.get_running_loop()
        client: BleakClient | None = None
        try:
            while True:
                cmd = await loop.run_in_executor(None, self._cmd.get)
                if cmd.kind == _CMD_STOP:
                    self._reconnect_address = None
                    break
                if cmd.kind == _CMD_SCAN:
                    await self._do_scan(cmd.args["timeout"])
                elif cmd.kind == _CMD_CONNECT:
                    self._reconnect_address = None
                    if client is not None:
                        await self._safe_disconnect(client)
                    client = await self._do_connect(cmd.args["address"])
                    if client is not None:
                        # 接続確立成功 → 以後の不意の切断は自動再接続する
                        self._reconnect_address = cmd.args["address"]
                elif cmd.kind == _CMD_DISCONNECT:
                    self._reconnect_address = None
                    if client is not None:
                        await self._safe_disconnect(client)
                        client = None
                elif cmd.kind == _CMD_SET_GRADE:
                    await self._send_grade(client, cmd.args["grade"])
                elif cmd.kind == _CMD_RECONNECT:
                    self._reconnect_pending = False
                    address = self._reconnect_address
                    if address is None:
                        continue  # 意図的切断済み → 再接続しない
                    if client is not None:
                        await self._safe_disconnect(client)
                        client = None
                    self.events.put(BridgeEvent("reconnecting", address))
                    client = await self._do_connect(address)
                    if client is None:
                        # 失敗 → 一定間隔をおいて無限リトライ
                        self._schedule_reconnect(_RECONNECT_RETRY_S)
        finally:
            if client is not None:
                await self._safe_disconnect(client)

    # --- スキャン ---

    async def _do_scan(self, timeout: float) -> None:
        try:
            devices = await BleakScanner.discover(
                timeout=timeout, return_adv=True
            )
        except Exception as e:
            self.events.put(BridgeEvent("error", f"scan failed: {e}"))
            self.events.put(BridgeEvent("scan_done"))
            return

        # 多くのセンサー（CYCPLUS C3 等）は広告パケットに 0x1816/0x1818 を載せない。
        # 広告UUIDでフィルタすると見えなくなるため、名前付きの全デバイスを候補にし、
        # 広告UUIDで分かる場合だけ profiles に印を付ける（参考情報）。
        # 実際のプロファイル判定は接続後の service discovery でやる（_do_connect）。
        for address, (device, adv) in devices.items():
            name = device.name or adv.local_name
            if not name:
                continue
            uuids = {u.lower() for u in (adv.service_uuids or [])}
            profiles: list[DeviceProfile] = []
            if U.CSC_SERVICE in uuids:
                profiles.append(DeviceProfile.CSC)
            if U.CPS_SERVICE in uuids:
                profiles.append(DeviceProfile.CPS)
            self.events.put(BridgeEvent(
                "scan_result",
                DeviceCandidate(
                    address=address,
                    name=name,
                    profiles=tuple(profiles),
                    rssi=getattr(adv, "rssi", None),
                ),
            ))
        self.events.put(BridgeEvent("scan_done"))

    # --- 接続 + 通知購読 ---

    async def _do_connect(self, address: str) -> BleakClient | None:
        self.events.put(BridgeEvent("connecting", address))
        client = BleakClient(address, disconnected_callback=self._on_disconnect)
        try:
            await client.connect()
        except Exception as e:
            self.events.put(BridgeEvent("error", f"connect failed: {e}"))
            return None

        # サービス一覧から実際のプロファイルを判定する。広告にUUIDが載っていない
        # デバイスもここで正しく判別できる。CPS と CSC 両対応なら CPS 優先。
        try:
            available = {s.uuid.lower() for s in client.services}
        except Exception as e:
            self.events.put(BridgeEvent("error", f"service discovery failed: {e}"))
            await self._safe_disconnect(client)
            return None

        # FE-C over BLE 対応か（トレーナーへの負荷制御に使う）
        self._fec_available = U.FEC_SERVICE in available

        if U.CPS_SERVICE in available:
            profile = DeviceProfile.CPS
        elif U.CSC_SERVICE in available:
            profile = DeviceProfile.CSC
        else:
            self.events.put(BridgeEvent(
                "error",
                "CSC/CPS どちらのサービスも見つかりませんでした",
            ))
            await self._safe_disconnect(client)
            return None

        try:
            features = await self._read_features(client, profile)
            await self._start_notify(client, profile)
        except Exception as e:
            self.events.put(BridgeEvent("error", f"setup failed: {e}"))
            await self._safe_disconnect(client)
            return None

        self.events.put(BridgeEvent("connected", {
            "address": address,
            "profile": profile,
            "features": features,
            "fec": self._fec_available,
        }))
        return client

    async def _send_grade(self, client: BleakClient | None, grade_pct: float) -> None:
        """FE-C RX へ Page 51 を書き込む。未接続・非対応なら何もしない。"""
        if client is None or not self._fec_available:
            return
        try:
            await client.write_gatt_char(
                U.FEC_RX, _build_fec_track_resistance(grade_pct)
            )
        except Exception as e:
            # 切断直後などに失敗し得る。定期再送されるのでログだけにする
            log.warning("FE-C grade write failed: %s", e)

    async def _read_features(
        self, client: BleakClient, profile: DeviceProfile
    ) -> dict[str, bool]:
        """Feature キャラを読んで wheel/crank/power 対応状況を返す。読めなければ
        notify 側で動的に判定するので空 dict でも問題ない。"""
        try:
            if profile is DeviceProfile.CSC:
                raw = await client.read_gatt_char(U.CSC_FEATURE)
                bits = int.from_bytes(raw[:2], "little") if len(raw) >= 2 else raw[0]
                return {
                    "wheel": bool(bits & CSC_FEATURE_WHEEL),
                    "crank": bool(bits & CSC_FEATURE_CRANK),
                    "power": False,
                }
            else:
                raw = await client.read_gatt_char(U.CPS_FEATURE)
                bits = int.from_bytes(raw[:4], "little") if len(raw) >= 4 \
                    else int.from_bytes(raw, "little")
                return {
                    "wheel": bool(bits & CPS_FEATURE_WHEEL),
                    "crank": bool(bits & CPS_FEATURE_CRANK),
                    "power": True,
                }
        except Exception as e:
            log.warning("feature read failed: %s", e)
            return {
                "wheel": True, "crank": True,
                "power": profile is DeviceProfile.CPS,
            }

    async def _start_notify(
        self, client: BleakClient, profile: DeviceProfile
    ) -> None:
        if profile is DeviceProfile.CSC:
            state = CscState()
            char_uuid = U.CSC_MEASUREMENT
        else:
            state = CpsState()
            char_uuid = U.CPS_MEASUREMENT

        def _handler(_char: Any, data: bytearray) -> None:
            try:
                tele: Telemetry = state.parse(bytes(data))
            except Exception as e:
                log.warning("parse error: %s (%s)", e, data.hex())
                return
            self.events.put(BridgeEvent("telemetry", tele))

        await client.start_notify(char_uuid, _handler)

    def _on_disconnect(self, _client: BleakClient) -> None:
        # bleak の callback は別タスク。Queue 経由でメインループへ。
        self.events.put(BridgeEvent("disconnected"))
        # 不意の切断（センサーのスリープ・電波途切れ等）→ 自動再接続を試みる。
        # 意図的切断中（_expect_disconnect）はここでは何もしない
        if not self._expect_disconnect:
            self._schedule_reconnect()

    def _schedule_reconnect(self, delay_s: float = 0.0) -> None:
        """再接続コマンドを（必要なら遅延付きで）投入する。BLEスレッドから呼ぶ。"""
        if self._reconnect_address is None or self._reconnect_pending:
            return
        self._reconnect_pending = True
        if delay_s > 0 and self._loop is not None:
            self._loop.call_later(
                delay_s, self._cmd.put, _Command(_CMD_RECONNECT)
            )
        else:
            self._cmd.put(_Command(_CMD_RECONNECT))

    async def _safe_disconnect(self, client: BleakClient) -> None:
        self._expect_disconnect = True
        try:
            await client.disconnect()
        except Exception as e:
            log.warning("disconnect failed: %s", e)
        finally:
            self._expect_disconnect = False
