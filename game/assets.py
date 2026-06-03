"""画像・フォントの読み込みと、スケール済みスプライトのキャッシュ。"""

import os

import pygame

from game import config as C

IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sozai", "images")


class Assets:
    def __init__(self) -> None:
        self.bg = pygame.image.load(os.path.join(IMAGE_DIR, "bg.png")).convert()
        self.wara = pygame.image.load(os.path.join(IMAGE_DIR, "wara.png")).convert_alpha()
        # 漕ぎアニメ用の2コマ（chari.png / chari2.png）
        w = C.PLAYER_SPRITE_W
        self.chari_frames: list[pygame.Surface] = []
        for name in ("chari.png", "chari2.png"):
            img = pygame.image.load(os.path.join(IMAGE_DIR, name)).convert_alpha()
            h = round(img.get_height() * w / img.get_width())
            self.chari_frames.append(pygame.transform.scale(img, (w, h)))
        self.chari = self.chari_frames[0]

        self.hud_font = pygame.font.SysFont("consolas", 36, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 80, bold=True)
        # 駅名など日本語表示用（Windows優先で順に試す）
        self.jp_hud_font = pygame.font.SysFont(
            "yugothicui,yugothic,meiryo,msgothic,consolas", 32, bold=True
        )

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
