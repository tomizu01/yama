"""勾配実装の動作確認用ワンショットスクリプト（ヘッドレス）。

- CSV の勾配カラム読込 → ステージの勾配（到着駅の値）
- FE-C Page 51 メッセージのエンコード
- ステージ付き Race の HUD 描画（GRADE 行）
- ステージ開始画面の描画（勾配表示）
"""

import os
import random
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from game import config as C
from game import stages as S
from game.assets import Assets
from game.ble.bridge import _build_fec_track_resistance
from game.race import Race, _draw_stage_start, _make_fonts
from game.speed_source import ConstantSpeedSource

OUT_DIR = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(OUT_DIR, exist_ok=True)

# --- 1) CSV 読込と勾配 ---
stations = S.load_stations(S.default_csv_path())
stages = S.build_stages(S.load_stations(S.default_csv_path()))
assert len(stages) == 30, len(stages)
by_label = {st.label: st for st in stages}
# 品川→大崎 は到着駅・大崎の勾配 1%
assert by_label["品川 → 大崎"].gradient_pct == 1.0
# 五反田→目黒 は目黒の 5%
assert by_label["五反田 → 目黒"].gradient_pct == 5.0
# 恵比寿→渋谷 は渋谷の -3%
assert by_label["恵比寿 → 渋谷"].gradient_pct == -3.0
print("CSV gradient OK")

# --- 2) FE-C Page 51 エンコード（docs の例と照合） ---
def hex_of(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

m0 = _build_fec_track_resistance(0.0)
assert m0[9] == 0x20 and m0[10] == 0x4E, hex_of(m0)   # 0% → 0x4E20
m5 = _build_fec_track_resistance(5.0)
assert m5[9] == 0x14 and m5[10] == 0x50, hex_of(m5)   # +5% → 0x5014
m_3 = _build_fec_track_resistance(-3.0)
assert m_3[9] == 0xF4 and m_3[10] == 0x4C, hex_of(m_3)  # -3% → 0x4CF4
assert m0[11] == 80  # CRR 0.004 → 0x50
for m in (m0, m5, m_3):
    chk = 0
    for x in m[:12]:
        chk ^= x
    assert m[12] == chk and len(m) == 13
print(f"FE-C encode OK  (+5% = {hex_of(m5)})")

# --- 3) 描画 ---
pygame.init()
pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
surface = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
assets = Assets()
fonts = _make_fonts()

stage = by_label["五反田 → 目黒"]  # +5%
race = Race(assets, ConstantSpeedSource(), stage=stage, rng=random.Random(42))
for _ in range(120):
    race.update(1 / 60, C.VP_X)
race.draw(surface)
pygame.image.save(surface, os.path.join(OUT_DIR, "gradient_hud.png"))

_draw_stage_start(surface, fonts, stage, assets.bg)
pygame.image.save(surface, os.path.join(OUT_DIR, "gradient_start.png"))
print("screenshots saved")
print("OK")
