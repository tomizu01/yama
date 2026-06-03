"""プレイヤー（自転車）。マウスX座標で左右移動のみ。"""

import pygame

from game import config as C
from game.assets import Assets


class Player:
    def __init__(self) -> None:
        self.u = 0.0  # 道路上の横位置（中心=0, 道路端=±1）
        self.anim_timer = 0.0  # 漕ぎアニメの経過時間
        self.frame = 0         # 現在のコマ（0=chari, 1=chari2）

    @property
    def screen_x(self) -> float:
        return C.VP_X + self.u * C.ROAD_HALF_W

    def update(self, dt: float, mouse_x: float, pedaling: bool = True) -> None:
        """マウスカーソルが自分より左なら左へ、右なら右へ動く。"""
        # 漕いでいる間は 1/3 秒毎に chari/chari2 を切り替える
        if pedaling:
            self.anim_timer += dt
            if self.anim_timer >= C.PLAYER_ANIM_INTERVAL_S:
                self.anim_timer -= C.PLAYER_ANIM_INTERVAL_S
                self.frame = 1 - self.frame
        else:
            self.anim_timer = 0.0
            self.frame = 0
        target_u = (mouse_x - C.VP_X) / C.ROAD_HALF_W
        target_u = max(-C.PLAYER_U_LIMIT, min(C.PLAYER_U_LIMIT, target_u))
        diff = target_u - self.u
        step = C.LATERAL_SPEED * dt
        if abs(diff) <= step:
            self.u = target_u
        else:
            self.u += step if diff > 0 else -step

    def draw(self, surface: pygame.Surface, assets: Assets) -> None:
        sprite = assets.chari_frames[self.frame]
        x = round(self.screen_x - sprite.get_width() / 2)
        y = round(C.PLAYER_Y - sprite.get_height())
        surface.blit(sprite, (x, y))
