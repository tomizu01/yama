"""路線のステージデータ（駅一覧 → 区間ステージ）。

CSV: `lines/<name>.csv` 形式
    駅名,緯度,経度

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


@dataclass(frozen=True)
class Station:
    name: str
    lat: float
    lon: float


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


def load_stations(csv_path: str) -> list[Station]:
    stations: list[Station] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not row[0].strip():
                continue
            name, lat_s, lon_s = row[0], row[1], row[2]
            stations.append(Station(name=name.strip(), lat=float(lat_s), lon=float(lon_s)))
    return stations


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
            norma_s=d / (NORMA_KMH / 3.6),   # NORMA_KMH を m/s に変換して割る
        ))
    return out


def default_csv_path() -> str:
    """リポジトリ直下の lines/yamanote.csv を返す。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "lines", "yamanote.csv")


def format_mmss(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
