"""画像・フォントの読み込みと、スケール済みスプライトのキャッシュ。"""

import os

import pygame

from game import config as C

IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sozai", "images")


class Assets:
    def __init__(self) -> None:
        self.bg = pygame.image.load(os.path.join(IMAGE_DIR, "bg.png")).convert()
        self.wara = pygame.image.load(os.path.join(IMAGE_DIR, "wara.png")).convert_alpha()
        chari = pygame.image.load(os.path.join(IMAGE_DIR, "chari.png")).convert_alpha()

        w = C.PLAYER_SPRITE_W
        h = round(chari.get_height() * w / chari.get_width())
        self.chari = pygame.transform.scale(chari, (w, h))

        self.hud_font = pygame.font.SysFont("consolas", 36, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 80, bold=True)

        # 藁はフレーム毎に大きさが変わるため、幅(px)ごとにスケール結果をキャッシュ
        self._wara_cache: dict[int, pygame.Surface] = {}

    def wara_scaled(self, width: int) -> pygame.Surface:
        width = max(2, width)
        surf = self._wara_cache.get(width)
        if surf is None:
            # transform.scale（ニアレスト）でレトロなドット感を保つ
            surf = pygame.transform.scale(self.wara, (width, width))
            self._wara_cache[width] = surf
        return surf
