"""レース画面（フェーズ1: 常時走行・障害物回避）。"""

import random

import pygame

from game import config as C
from game.assets import Assets
from game.obstacles import ObstacleField
from game.player import Player
from game.speed_source import ConstantSpeedSource, SpeedSource


class Race:
    """レースの状態と更新・描画。run() からもテストハーネスからも使う。"""

    def __init__(self, assets: Assets, speed_source: SpeedSource,
                 rng: random.Random | None = None) -> None:
        self.assets = assets
        self.speed_source = speed_source
        self.player = Player()
        self.field = ObstacleField(rng)
        self.distance_m = 0.0     # 走行距離
        self.speed_mult = 1.0     # 衝突ペナルティ（1.0 = 通常）
        self.hit_timer = 0.0      # "HIT!" 表示の残り時間
        self.flash_timer = 0.0    # 画面フラッシュの残り時間

    @property
    def effective_kmh(self) -> float:
        return self.speed_source.speed_kmh * self.speed_mult

    def update(self, dt: float, mouse_x: float) -> None:
        self.speed_source.update(dt)

        # ペナルティの回復
        self.speed_mult = min(1.0, self.speed_mult + C.HIT_RECOVERY_PER_S * dt)
        self.hit_timer = max(0.0, self.hit_timer - dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)

        # 前進
        d_prev = self.distance_m
        self.distance_m += self.effective_kmh / 3.6 * C.VISUAL_SPEED_FACTOR * dt

        # 左右移動
        self.player.update(dt, mouse_x)

        # 障害物の更新と衝突
        hits = self.field.update(d_prev, self.distance_m, self.player.u)
        if hits:
            self.speed_mult = C.HIT_SPEED_MULT
            self.hit_timer = 1.0
            self.flash_timer = 0.25

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.assets.bg, (0, 0))
        self.field.draw(surface, self.assets, self.distance_m)
        self.player.draw(surface, self.assets)
        self._draw_hud(surface)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        font = self.assets.hud_font
        lines = [
            f"SPEED {self.effective_kmh:5.1f} km/h",
            f"DIST  {self.distance_m:6.0f} m",
        ]
        for i, text in enumerate(lines):
            y = 16 + i * 44
            surface.blit(font.render(text, True, (0, 0, 0)), (22, y + 2))
            surface.blit(font.render(text, True, (255, 255, 255)), (20, y))

        if self.hit_timer > 0:
            msg = self.assets.big_font.render("HIT!", True, (255, 60, 40))
            rect = msg.get_rect(center=(C.VP_X, 320))
            surface.blit(msg, rect)

        if self.flash_timer > 0:
            flash = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
            flash.fill((255, 0, 0))
            flash.set_alpha(70)
            surface.blit(flash, (0, 0))


def run() -> None:
    pygame.init()
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.SCALED)
    pygame.display.set_caption("山手線大冒険")
    clock = pygame.time.Clock()

    assets = Assets()
    speed_source = ConstantSpeedSource()
    race = Race(assets, speed_source)

    running = True
    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                # 開発用: ↑↓で巡航速度を調整（フェーズ2で実速度に置き換わる）
                elif event.key == pygame.K_UP:
                    speed_source.adjust(+C.DEBUG_SPEED_STEP)
                elif event.key == pygame.K_DOWN:
                    speed_source.adjust(-C.DEBUG_SPEED_STEP)

        mouse_x, _ = pygame.mouse.get_pos()
        race.update(dt, mouse_x)
        race.draw(screen)
        pygame.display.flip()

    speed_source.close()
    pygame.quit()
