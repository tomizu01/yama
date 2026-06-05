"""路線選択の動作確認用ワンショットスクリプト（ヘッドレス）。

- available_lines() の一覧と並び順
- 両CSVの読込・ステージ生成・勾配
- 勾配バリデーション（不正値で ValueError）
- run_line_select の描画（タイマーで QUIT を投げて最終フレームを保存）
"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from game import display as D
from game import stages as S

OUT_DIR = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(OUT_DIR, exist_ok=True)

# --- 1) 路線一覧 ---
lines = S.available_lines()
keys = [l.key for l in lines]
assert keys == ["yamanote", "keihin_tohoku"], keys  # 表示名辞書の順
assert lines[0].name == "山手線" and lines[1].name == "京浜東北線"
print("available_lines OK:", [(l.key, l.name) for l in lines])

# --- 2) 各CSVの読込とステージ生成 ---
for line in lines:
    stages = S.build_stages(S.load_stations(line.csv_path))
    total_km = sum(st.distance_m for st in stages) / 1000.0
    grads = sorted({st.gradient_pct for st in stages})
    print(f"  {line.name}: {len(stages)} stages, {total_km:.1f} km, gradients={grads}")
yt = S.build_stages(S.load_stations(lines[1].csv_path))
by_label = {st.label: st for st in yt}
assert by_label["新杉田 → 洋光台"].gradient_pct == 5.0   # 到着駅の勾配
assert by_label["港南台 → 本郷台"].gradient_pct == -4.0
assert yt[0].start.name == "大宮" and yt[-1].goal.name == "大船"  # 直線路線（非周回）
print("keihin_tohoku gradients OK")

# --- 3) 勾配バリデーション（緯度の重複カラム混入を模擬） ---
import tempfile
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                 encoding="utf-8") as f:
    f.write("大宮,35.906295,139.623999,35.906295,139.623999,0\n")
    bad_path = f.name
try:
    S.load_stations(bad_path)
    raise AssertionError("ValueError expected")
except ValueError as e:
    print("validation OK:", e)
finally:
    os.unlink(bad_path)

# --- 4) 路線選択画面の描画 ---
pygame.init()
D.init()
screen = D.surface()
clock = pygame.time.Clock()

from game.menu import run_line_select
from game.speed_source import ConstantSpeedSource

pygame.time.set_timer(pygame.QUIT, 700)  # 0.7秒後に QUIT → None で戻る
result = run_line_select(screen, clock, ConstantSpeedSource())
assert result is None
pygame.image.save(screen, os.path.join(OUT_DIR, "line_select.png"))
print("screenshot saved")
print("OK")
