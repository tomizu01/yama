"""障害物（藁）の生成・更新・描画。

藁は世界座標上で静止しており、プレイヤーが進むことで相対的に
手前へ「降りてくる」ように見える。
"""

import random
from dataclasses import dataclass, field

import pygame

from game import config as C
from game.assets import Assets
from game.projection import project


@dataclass
class Obstacle:
    z_world: float  # スタート地点からの絶対距離 [m]
    u: float        # 道路上の横位置
    hit: bool = field(default=False)  # 一度ぶつかったら再判定しない


class ObstacleField:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.obstacles: list[Obstacle] = []
        self._next_spawn_d = 40.0  # 最初の列が出る距離（スタート直後は空ける）

    def update(self, player_d_prev: float, player_d: float, player_u: float) -> int:
        """生成・破棄・衝突判定を行い、このフレームの衝突数を返す。"""
        # 出現: プレイヤー前方 Z_SPAWN まで列を補充
        while self._next_spawn_d < player_d + C.Z_SPAWN:
            self._spawn_row(self._next_spawn_d)
            self._next_spawn_d += self.rng.uniform(C.SPAWN_GAP_MIN, C.SPAWN_GAP_MAX)

        # 衝突: このフレームでプレイヤー平面 (z=0) を通過した藁を判定
        hits = 0
        for ob in self.obstacles:
            if not ob.hit and player_d_prev < ob.z_world <= player_d:
                if abs(ob.u - player_u) < C.HIT_U_DIST:
                    ob.hit = True
                    hits += 1

        # 破棄: 通過済みの藁を削除
        self.obstacles = [
            ob for ob in self.obstacles if ob.z_world - player_d > C.Z_DESPAWN
        ]
        return hits

    def _spawn_row(self, z_world: float) -> None:
        """1列分の藁を生成する。

        4レーン中最大2レーンにしか置かないため、必ず通り道が残る。
        """
        n = self.rng.randint(1, C.MAX_WARA_PER_ROW)
        lanes = self.rng.sample(C.LANE_SLOTS, n)
        for lane in lanes:
            u = lane + self.rng.uniform(-C.LANE_JITTER, C.LANE_JITTER)
            self.obstacles.append(Obstacle(z_world=z_world, u=u))

    def draw(self, surface: pygame.Surface, assets: Assets, player_d: float) -> None:
        # 遠いものから順に描く（手前の藁が上に重なる）
        for ob in sorted(self.obstacles, key=lambda o: o.z_world, reverse=True):
            z = ob.z_world - player_d
            if z < -2.0:
                continue  # 画面下へ抜けきった藁
            x, y, scale = project(z, ob.u)
            width = round(C.WARA_FRONT_W * scale)
            if width < 3:
                continue
            sprite = assets.wara_scaled(width)
            surface.blit(sprite, (round(x - width / 2), round(y - sprite.get_height())))
