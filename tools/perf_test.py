"""ヘッドレスで update+draw を回してフレーム処理時間を計測する開発用スクリプト。"""

import os
import random
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from game import config as C
from game.assets import Assets
from game.race import Race
from game.speed_source import ConstantSpeedSource

pygame.init()
pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
surface = pygame.Surface((C.SCREEN_W, C.SCREEN_H))

race = Race(Assets(), ConstantSpeedSource(), rng=random.Random(7))

N = 600  # 10秒分
start = time.perf_counter()
for i in range(N):
    race.update(1 / 60, C.VP_X + (i % 200) - 100)
    race.draw(surface)
elapsed = time.perf_counter() - start
print(f"{N} frames in {elapsed:.2f}s -> {elapsed / N * 1000:.2f} ms/frame "
      f"(60fps budget: 16.7ms)")
