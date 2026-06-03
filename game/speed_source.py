"""走行速度の入力源の抽象化。

フェーズ1では固定速度のモック。フェーズ2で BLE（CSC / CPS+FE-C）実装に
差し替えられるよう、同じインターフェースを実装する。
"""

from game import config as C


class SpeedSource:
    """ライダーの現在速度を供給するインターフェース。"""

    def update(self, dt: float) -> None:
        pass

    @property
    def speed_kmh(self) -> float:
        raise NotImplementedError

    def close(self) -> None:
        pass


class ConstantSpeedSource(SpeedSource):
    """フェーズ1用: 常に一定速度で走り続けるモック。

    開発用に adjust() で速度を変えられる（↑↓キー）。
    """

    def __init__(self, kmh: float = C.CRUISE_KMH) -> None:
        self._kmh = kmh

    @property
    def speed_kmh(self) -> float:
        return self._kmh

    def adjust(self, delta_kmh: float) -> None:
        self._kmh = max(0.0, min(80.0, self._kmh + delta_kmh))
