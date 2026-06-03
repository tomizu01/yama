"""CSC Measurement (0x2A5B) と CPS Measurement (0x2A63) のパース。

- ロールオーバー処理付きで delta から speed_kmh / cadence_rpm を計算する。
- CSC のホイールタイムは 1/1024 秒、CPS のホイールタイムは **1/2048 秒**。
  間違えると速度が2倍ズレるので注意（aicyc-CLAUDE.md / docs/ble-cps-profile.md 参照）。
- クランクタイムは CSC/CPS とも 1/1024 秒。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


# --- ロールオーバー定数 ---
WHEEL_REVS_ROLL = 1 << 32   # CSC/CPS とも 32bit
CRANK_REVS_ROLL = 1 << 16   # CSC/CPS とも 16bit
TIME_ROLL = 1 << 16         # ホイール/クランクとも 16bit


@dataclass
class Telemetry:
    """1回の Measurement 通知から得られたテレメトリ。

    取れなかった項目は None のまま。
    """
    power_w: float | None = None       # 瞬時パワー [W] (CPSのみ)
    speed_kmh: float | None = None     # ホイール delta から算出した速度
    cadence_rpm: float | None = None   # クランク delta から算出したケイデンス


def _delta(curr: int, prev: int, rollover: int) -> int:
    d = curr - prev
    if d < 0:
        d += rollover
    return d


@dataclass
class _RevState:
    """ホイール/クランクの「累積回転 + タイムスタンプ」用の差分計算 state。"""
    prev_revs: int | None = None
    prev_time: int | None = None

    def step(self, revs: int, time_raw: int, ticks_per_sec: int,
             revs_rollover: int) -> tuple[int, float] | None:
        """前回値と比較して (delta_revs, delta_seconds) を返す。
        初回 or 時間差0 の場合は None。
        """
        if self.prev_revs is None:
            self.prev_revs = revs
            self.prev_time = time_raw
            return None
        d_revs = _delta(revs, self.prev_revs, revs_rollover)
        d_ticks = _delta(time_raw, self.prev_time, TIME_ROLL)
        self.prev_revs = revs
        self.prev_time = time_raw
        if d_ticks == 0:
            return None
        return d_revs, d_ticks / ticks_per_sec


# ---------------------------------------------------------------------------
# CSC (0x2A5B)
# ---------------------------------------------------------------------------

CSC_FLAG_WHEEL = 0x01
CSC_FLAG_CRANK = 0x02


@dataclass
class CscState:
    """CSC 用の差分計算 state。インスタンス1個を接続中ずっと使い回す。"""
    wheel_circumference_mm: int = 2105   # 700×25c
    _wheel: _RevState = None  # type: ignore[assignment]
    _crank: _RevState = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._wheel = _RevState()
        self._crank = _RevState()

    def parse(self, data: bytes) -> Telemetry:
        if len(data) < 1:
            return Telemetry()
        flags = data[0]
        offset = 1
        t = Telemetry()

        if flags & CSC_FLAG_WHEEL:
            if len(data) < offset + 6:
                return t
            revs = struct.unpack_from("<I", data, offset)[0]
            time_raw = struct.unpack_from("<H", data, offset + 4)[0]
            offset += 6
            r = self._wheel.step(revs, time_raw, ticks_per_sec=1024,
                                 revs_rollover=WHEEL_REVS_ROLL)
            if r is not None:
                d_revs, d_sec = r
                wheel_m = self.wheel_circumference_mm / 1000.0
                t.speed_kmh = d_revs * wheel_m / d_sec * 3.6

        if flags & CSC_FLAG_CRANK:
            if len(data) < offset + 4:
                return t
            revs = struct.unpack_from("<H", data, offset)[0]
            time_raw = struct.unpack_from("<H", data, offset + 2)[0]
            offset += 4
            r = self._crank.step(revs, time_raw, ticks_per_sec=1024,
                                 revs_rollover=CRANK_REVS_ROLL)
            if r is not None:
                d_revs, d_sec = r
                t.cadence_rpm = (d_revs / d_sec) * 60.0

        return t


# ---------------------------------------------------------------------------
# CPS (0x2A63)
# ---------------------------------------------------------------------------

CPS_FLAG_PEDAL_BALANCE = 0x0001
CPS_FLAG_ACC_TORQUE = 0x0004
CPS_FLAG_WHEEL = 0x0010
CPS_FLAG_CRANK = 0x0020


@dataclass
class CpsState:
    """CPS 用の差分計算 state。"""
    wheel_circumference_mm: int = 2105
    _wheel: _RevState = None  # type: ignore[assignment]
    _crank: _RevState = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._wheel = _RevState()
        self._crank = _RevState()

    def parse(self, data: bytes) -> Telemetry:
        if len(data) < 4:
            return Telemetry()
        flags = struct.unpack_from("<H", data, 0)[0]
        power = struct.unpack_from("<h", data, 2)[0]  # signed
        offset = 4
        t = Telemetry(power_w=float(power))

        if flags & CPS_FLAG_PEDAL_BALANCE:
            offset += 1
        if flags & CPS_FLAG_ACC_TORQUE:
            offset += 2

        if flags & CPS_FLAG_WHEEL:
            if len(data) < offset + 6:
                return t
            revs = struct.unpack_from("<I", data, offset)[0]
            time_raw = struct.unpack_from("<H", data, offset + 4)[0]
            offset += 6
            # CPS は 1/2048 秒解像度
            r = self._wheel.step(revs, time_raw, ticks_per_sec=2048,
                                 revs_rollover=WHEEL_REVS_ROLL)
            if r is not None:
                d_revs, d_sec = r
                wheel_m = self.wheel_circumference_mm / 1000.0
                t.speed_kmh = d_revs * wheel_m / d_sec * 3.6

        if flags & CPS_FLAG_CRANK:
            if len(data) < offset + 4:
                return t
            revs = struct.unpack_from("<H", data, offset)[0]
            time_raw = struct.unpack_from("<H", data, offset + 2)[0]
            offset += 4
            # クランクは 1/1024 秒解像度
            r = self._crank.step(revs, time_raw, ticks_per_sec=1024,
                                 revs_rollover=CRANK_REVS_ROLL)
            if r is not None:
                d_revs, d_sec = r
                t.cadence_rpm = (d_revs / d_sec) * 60.0

        return t


# ---------------------------------------------------------------------------
# Feature ビット (Feature キャラクタリスティックの解釈用)
# ---------------------------------------------------------------------------

CSC_FEATURE_WHEEL = 0x01
CSC_FEATURE_CRANK = 0x02

CPS_FEATURE_WHEEL = 0x04   # bit 2
CPS_FEATURE_CRANK = 0x08   # bit 3
