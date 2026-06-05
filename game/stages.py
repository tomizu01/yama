"""路線のステージデータ（駅一覧 → 区間ステージ）。

CSV: `lines/<name>.csv` 形式
    駅名,緯度,経度,勾配[%]
（勾配カラムは省略可。各ステージの勾配は「到着駅」の値を使う。
  例: 東京→有楽町 は有楽町の勾配で走る）

距離計算は概算。
  緯度1度 ≒ 111 km
  経度1度 ≒ 91 km （東京緯度 35° の場合の cos(35°) × 111km ≒ 91km）
※ ユーザー仕様には「経度1度≒91m」とあったが単位の表記揺れで、
  実際に必要な値は 91km（91000m）。

最終駅（CSVの末尾）は周回を閉じる東京駅（1駅目と同じ座標）を入れておくことで、
連続した駅ペアを単純に enumerate するだけで N ステージが作れる。
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass


# --- 距離概算用の係数 ---
M_PER_DEG_LAT = 111_000.0
M_PER_DEG_LON = 91_000.0   # 東京緯度の概算

NORMA_KMH = 25.0

# 勾配によるノルマ時間の補正（2026-06-05 ユーザー指定）:
#   勾配 +1% につき ノルマ時間 +10%（最大 +200% = 3倍）
#   勾配 -1% につき ノルマ時間 -10%（最大 -50% = 半分）
NORMA_GRADIENT_PER_PCT = 0.10
NORMA_GRADIENT_FACTOR_MAX = 3.0
NORMA_GRADIENT_FACTOR_MIN = 0.5

# CSV ファイル名（拡張子なし）→ 画面に出す路線名。
# この辞書の順序が路線選択画面の並び順になる（未登録の CSV は末尾、key 名で表示）
LINE_DISPLAY_NAMES = {
    "yamanote": "山手線",
    "keihin_tohoku": "京浜東北線",
    "keihin_tohoku_north": "京浜東北線（北）",
    "keihin_tohoku_south": "京浜東北線（南）",
}

# 勾配としてあり得ない値はデータミスとして弾く（緯度経度の重複カラム等の混入検出）
_MAX_ABS_GRADIENT = 30.0


@dataclass(frozen=True)
class Line:
    """選択可能な路線（lines/ ディレクトリの CSV 1つに対応）。"""
    key: str        # ファイル名（拡張子なし）
    name: str       # 表示名（日本語）
    csv_path: str


@dataclass(frozen=True)
class Station:
    name: str
    lat: float
    lon: float
    gradient_pct: float = 0.0   # この駅へ向かう区間の勾配 [%]


@dataclass(frozen=True)
class Stage:
    index: int          # 1始まり
    total: int          # 全ステージ数
    start: Station
    goal: Station
    distance_m: float
    norma_s: float

    @property
    def label(self) -> str:
        return f"{self.start.name} → {self.goal.name}"

    @property
    def gradient_pct(self) -> float:
        """ステージ走行中の勾配 [%]。到着駅の値を使う。"""
        return self.goal.gradient_pct


def load_stations(csv_path: str) -> list[Station]:
    stations: list[Station] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not row[0].strip():
                continue
            name, lat_s, lon_s = row[0], row[1], row[2]
            grad = float(row[3]) if len(row) >= 4 and row[3].strip() else 0.0
            if abs(grad) > _MAX_ABS_GRADIENT:
                raise ValueError(
                    f"{os.path.basename(csv_path)} の駅「{name.strip()}」の勾配が "
                    f"{grad} % です。カラムは 駅名,緯度,経度,勾配[%] の4列に"
                    "なっているか確認してください（緯度経度の重複カラム混入の疑い）"
                )
            stations.append(Station(
                name=name.strip(), lat=float(lat_s), lon=float(lon_s),
                gradient_pct=grad,
            ))
    return stations


def norma_gradient_factor(gradient_pct: float) -> float:
    """勾配 [%] → ノルマ時間に掛ける倍率（0.5〜3.0 にクランプ）。"""
    f = 1.0 + gradient_pct * NORMA_GRADIENT_PER_PCT
    return max(NORMA_GRADIENT_FACTOR_MIN, min(NORMA_GRADIENT_FACTOR_MAX, f))


def approx_distance_m(a: Station, b: Station) -> float:
    """簡易距離（緯度1度≒111km、経度1度≒91km）。"""
    dy = (b.lat - a.lat) * M_PER_DEG_LAT
    dx = (b.lon - a.lon) * M_PER_DEG_LON
    return math.hypot(dx, dy)


def build_stages(stations: list[Station]) -> list[Stage]:
    """連続する駅ペアからステージを作る。CSV末尾に周回閉じ用の駅を入れておくこと。"""
    pairs = list(zip(stations[:-1], stations[1:]))
    total = len(pairs)
    out: list[Stage] = []
    for i, (a, b) in enumerate(pairs, start=1):
        d = approx_distance_m(a, b)
        out.append(Stage(
            index=i, total=total,
            start=a, goal=b,
            distance_m=d,
            # NORMA_KMH を m/s に変換して割り、勾配（到着駅の値）で時間を補正
            norma_s=d / (NORMA_KMH / 3.6) * norma_gradient_factor(b.gradient_pct),
        ))
    return out


def lines_dir() -> str:
    """リポジトリ直下の lines/ ディレクトリを返す。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "lines")


def available_lines() -> list[Line]:
    """lines/*.csv を路線一覧として返す。LINE_DISPLAY_NAMES の順 → 未登録は名前順。"""
    known_order = list(LINE_DISPLAY_NAMES)
    found: list[Line] = []
    for fn in sorted(os.listdir(lines_dir())):
        if not fn.lower().endswith(".csv"):
            continue
        key = os.path.splitext(fn)[0]
        found.append(Line(
            key=key,
            name=LINE_DISPLAY_NAMES.get(key, key),
            csv_path=os.path.join(lines_dir(), fn),
        ))
    found.sort(key=lambda l: (known_order.index(l.key)
                              if l.key in known_order else len(known_order)))
    return found


def default_csv_path() -> str:
    """リポジトリ直下の lines/yamanote.csv を返す（開発ツール用）。"""
    return os.path.join(lines_dir(), "yamanote.csv")


def format_mmss(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
