"""疑似3D投影。

世界座標 (z, u) をスクリーン座標に変換する。
  z: プレイヤーからの前方距離 [m]（0 = プレイヤー平面）
  u: 道路上の横位置（中心 = 0, 道路端 = ±1）
"""

from game import config as C


def project(z: float, u: float) -> tuple[float, float, float]:
    """(z, u) → (screen_x, screen_y, scale) を返す。

    scale はプレイヤー平面 (z=0) で 1.0、遠くなるほど 0 に近づく。
    `PERSPECTIVE_POWER > 1` で「遠くは控えめ／手前で一気に迫る」加速感が強まる。
    """
    # z < 0（プレイヤー通過後）も少しだけ許容し、画面下へ滑り抜ける動きを作る
    t_base = C.Z_NEAR / (C.Z_NEAR + max(z, -C.Z_NEAR * 0.5))
    t = t_base ** C.PERSPECTIVE_POWER
    x = C.VP_X + u * C.ROAD_HALF_W * t
    y = C.VP_Y + (C.PLAYER_Y - C.VP_Y) * t
    return x, y, t
