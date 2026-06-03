"""ヘッドレスでゲームを数秒分シミュレートし、スクリーンショットを保存する開発用スクリプト。"""

import os
import random
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from game import config as C
from game.assets import Assets
from game.race import Race
from game.speed_source import ConstantSpeedSource

OUT_DIR = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(OUT_DIR, exist_ok=True)

pygame.init()
pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
surface = pygame.Surface((C.SCREEN_W, C.SCREEN_H))

assets = Assets()
race = Race(assets, ConstantSpeedSource(), rng=random.Random(42))

DT = 1 / 60
SHOT_TIMES = [0.5, 4.0, 8.0, 12.0]
# マウスを時間帯で動かして左右移動も確認する
def mouse_x_at(t: float) -> float:
    if t < 4.0:
        return C.VP_X            # 中央キープ
    if t < 8.0:
        return C.VP_X - 600      # 左へ
    return C.VP_X + 600          # 右へ

t = 0.0
shot_idx = 0
hits_total = 0
while shot_idx < len(SHOT_TIMES):
    speed_mult_before = race.speed_mult
    race.update(DT, mouse_x_at(t))
    if race.hit_timer == 1.0 and speed_mult_before > C.HIT_SPEED_MULT:
        hits_total += 1
    t += DT
    if t >= SHOT_TIMES[shot_idx]:
        race.draw(surface)
        path = os.path.join(OUT_DIR, f"shot_{SHOT_TIMES[shot_idx]:04.1f}s.png")
        pygame.image.save(surface, path)
        print(f"saved {path}  dist={race.distance_m:.1f}m  speed={race.effective_kmh:.1f}km/h  "
              f"obstacles={len(race.field.obstacles)}  player_u={race.player.u:+.2f}")
        shot_idx += 1

print(f"hits during run: {hits_total}")
print("OK")
