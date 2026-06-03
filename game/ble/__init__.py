"""BLE（CSC / CPS）連携モジュール。

- `parser`: CSC Measurement / CPS Measurement のバイト列パース
- `bridge`: bleak を asyncio 専用スレッドで回し、ゲーム側と Queue でやり取りする
"""

from game.ble.bridge import (
    BleBridge,
    BridgeEvent,
    DeviceCandidate,
    DeviceProfile,
)
from game.ble.parser import CscState, CpsState, Telemetry

__all__ = [
    "BleBridge",
    "BridgeEvent",
    "DeviceCandidate",
    "DeviceProfile",
    "CscState",
    "CpsState",
    "Telemetry",
]
