"""走行速度の入力源の抽象化。

- `ConstantSpeedSource`: 固定速度（デモ走行用）
- `BleSpeedSource`: BLE デバイスのテレメトリから飽和速度を算出 → 慣性シミュレーションで
  現在速度を緩やかに収束させる（aicyc-CLAUDE.md の式を移植）。

aicyc では 5Hz の固定更新で `speed += (sat - speed) * 0.05` だったため、200ms 当たり
5% 縮める実効時定数 τ ≈ −0.2 / ln(0.95) ≒ 3.9s。本実装は dt 不定の可変ループでも同じ
収束特性になるよう `1 - exp(-dt / τ)` を毎フレーム掛ける形にしている。
"""

from __future__ import annotations

import math
import queue
from enum import Enum

from game import config as C


# 慣性シミュレーションの時定数 [s]。aicyc の 5Hz×0.05 と同じ収束特性。
_INERTIA_TAU_S = 4.0
# テレメトリが何秒来なければ「停止」とみなすか
_STOP_TIMEOUT_S = 3.0
# テレメトリが何秒途絶えたら強制再接続を要求するか（切断 callback が来ない場合の保険）
_RECONNECT_WATCHDOG_S = 20.0


class Mode(Enum):
    """BLE 走行モード。どのテレメトリ値を「走行入力」として使うか。"""
    SPEED = "speed"        # ホイール回転 → 速度
    CADENCE = "cadence"    # クランク回転 → 速度（推定）
    POWER = "power"        # パワー → 速度（推定、CPS のみ）

    @property
    def label(self) -> str:
        return self.value.upper()


class SpeedSource:
    """ライダーの現在速度を供給するインターフェース。"""

    mode_label: str = "DEMO"
    status_text: str | None = None   # HUD に出す異常状態（None = 正常）

    def update(self, dt: float) -> None:
        pass

    @property
    def speed_kmh(self) -> float:
        raise NotImplementedError

    @property
    def cadence_rpm(self) -> float | None:
        return None

    @property
    def power_w(self) -> float | None:
        return None

    def close(self) -> None:
        pass


class ConstantSpeedSource(SpeedSource):
    """フェーズ1用・デモ走行用: 常に一定速度。

    開発用に adjust() で速度を変えられる（↑↓キー）。
    """

    mode_label = "DEMO"

    def __init__(self, kmh: float = C.CRUISE_KMH) -> None:
        self._kmh = kmh

    @property
    def speed_kmh(self) -> float:
        return self._kmh

    def adjust(self, delta_kmh: float) -> None:
        self._kmh = max(0.0, min(80.0, self._kmh + delta_kmh))


class BleSpeedSource(SpeedSource):
    """BLE テレメトリから飽和速度を算出して慣性で収束させる。

    `bridge.events` を毎フレーム drain して最新のテレメトリを保持し、`update(dt)`
    のたびに飽和速度 → 現在速度を更新する。`gradient` はフェーズ3でステージ実装後に
    流し込む想定で、現状は常に 0。
    """

    def __init__(self, bridge, mode: Mode, gradient_pct: float = 0.0) -> None:
        self.bridge = bridge
        self.mode = mode
        self.mode_label = mode.label
        self.gradient_pct = gradient_pct

        self._speed_kmh = 0.0
        self._sensor_speed_kmh: float | None = None
        self._cadence_rpm: float | None = None
        self._power_w: float | None = None

        self._t = 0.0
        self._last_telemetry_at = 0.0
        self._got_first_telemetry = False

        # bridge 由来のエラー/切断を記録（HUD に出してもよいが今は内部保持のみ）
        self.last_status: str | None = None

    @property
    def speed_kmh(self) -> float:
        return self._speed_kmh

    @property
    def cadence_rpm(self) -> float | None:
        return self._cadence_rpm

    @property
    def power_w(self) -> float | None:
        return self._power_w

    def update(self, dt: float) -> None:
        self._t += dt

        # 1) BLE スレッドからのイベントを drain
        self._drain_events()

        # 2) 停止検出
        if (self._got_first_telemetry
                and self._t - self._last_telemetry_at > _STOP_TIMEOUT_S):
            self._sensor_speed_kmh = 0.0
            self._cadence_rpm = 0.0
            self._power_w = 0.0

        # 2.5) テレメトリ途絶ウォッチドッグ。bleak の切断 callback が来ないまま
        # 接続が死んでいるケースの保険として、強制再接続を要求する。
        # （単に漕いでいないだけでセンサーが通知を止めている場合も再接続が走るが、
        #   速度は既に0なので実害はない）
        if (self._got_first_telemetry
                and self._t - self._last_telemetry_at > _RECONNECT_WATCHDOG_S):
            self.bridge.request_reconnect()
            self._last_telemetry_at = self._t  # 再アーム（毎フレーム要求しない）
            self.status_text = "RECONNECT..."

        # 3) 飽和速度を計算
        sat = self._saturation_kmh()

        # 4) 慣性で current → saturation に収束
        alpha = 1.0 - math.exp(-dt / _INERTIA_TAU_S)
        self._speed_kmh += (sat - self._speed_kmh) * alpha

    def _drain_events(self) -> None:
        while True:
            try:
                ev = self.bridge.events.get_nowait()
            except queue.Empty:
                return
            if ev.kind == "telemetry":
                t = ev.payload
                touched = False
                if t.speed_kmh is not None:
                    self._sensor_speed_kmh = t.speed_kmh
                    touched = True
                if t.cadence_rpm is not None:
                    self._cadence_rpm = t.cadence_rpm
                    touched = True
                if t.power_w is not None:
                    self._power_w = t.power_w
                    touched = True
                if touched:
                    self._last_telemetry_at = self._t
                    self._got_first_telemetry = True
            elif ev.kind in ("disconnected", "reconnecting"):
                # bridge が自動再接続中。復帰（connected）まで HUD に出す
                self.last_status = ev.kind
                self.status_text = "RECONNECT..."
            elif ev.kind == "connected":
                self.last_status = ev.kind
                self.status_text = None
                # 再接続直後の停止検出/ウォッチドッグ誤発動を防ぐ
                self._last_telemetry_at = self._t
            elif ev.kind == "error":
                self.last_status = ev.kind
            # その他の kind（接続中などレース前のイベント）は無視

    def _saturation_kmh(self) -> float:
        """aicyc-CLAUDE.md の式をそのまま移植。

        | mode    | 飽和速度 (gradient=0 想定で簡略化していない) |
        |---------|--------------------------------------------|
        | speed   | センサー速度                                 |
        | cadence | 勾配 > -1%: cadence/3 - g*2 (cadence≤30で0) |
        |         | 勾配 ≤ -1%: 20 + max(cadence-60,0)/3 - g*2  |
        | power   | 勾配 > 1% かつ power ≤ 30W: 0               |
        |         | それ以外: log10(3 + max(power - g*20, 0.5)) * 15 |
        """
        g = self.gradient_pct
        if self.mode is Mode.SPEED:
            return self._sensor_speed_kmh or 0.0

        if self.mode is Mode.CADENCE:
            cad = self._cadence_rpm or 0.0
            if g > -1.0:
                if cad <= 30.0:
                    return 0.0
                return cad / 3.0 - g * 2.0
            else:
                return 20.0 + max(cad - 60.0, 0.0) / 3.0 - g * 2.0

        # POWER
        p = self._power_w or 0.0
        if g > 1.0 and p <= 30.0:
            return 0.0
        return math.log10(3.0 + max(p - g * 20.0, 0.5)) * 15.0

    def close(self) -> None:
        # bridge は menu が所有・破棄するためここでは何もしない（責任分離）
        pass
