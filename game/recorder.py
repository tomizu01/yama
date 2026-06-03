"""GPXトラック記録。

ステージ進捗から (緯度, 経度) を線形補完して5秒おきに記録する。緯度経度の厳密な
大圏計算はせず、単純な start↔goal の直線補間（仕様: 概算でよい）。

セッション全体（複数ステージ）にまたがって点を蓄積する。`write_gpx()` でいつでも
ファイル出力可能（クリア画面の「gpxを記録する」ボタンから呼ばれる）。
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from game.stages import Stage


SAMPLE_INTERVAL_S = 5.0


@dataclass(frozen=True)
class TrackPoint:
    lat: float
    lon: float
    time: dt.datetime  # UTC


@dataclass
class TrackRecorder:
    """セッション全体のGPX記録。Race の update から `tick()` で点を増やす。"""

    line_name: str = "山手線"
    points: list[TrackPoint] = field(default_factory=list)

    # 内部時刻と直近サンプルの追跡
    _session_t: float = 0.0
    _next_check_t: float = 0.0
    _last_key: tuple[int, float] | None = None  # (stage.index, progress)

    def tick(self, dt_s: float, stage: Stage, progress_0_1: float) -> None:
        """Race.update から呼ぶ。5秒おきに進捗チェックして記録する。"""
        progress = max(0.0, min(1.0, progress_0_1))
        self._session_t += dt_s
        if self._session_t < self._next_check_t:
            return
        self._next_check_t = self._session_t + SAMPLE_INTERVAL_S

        # 「前回より進んでいたら」: 同ステージで progress <= 直近 ならスキップ。
        # 別ステージ（index が増えた）なら必ず記録する。
        if self._last_key is not None:
            li, lp = self._last_key
            if li == stage.index and progress <= lp:
                return

        self._record(stage, progress)

    def force_record_endpoint(self, stage: Stage) -> None:
        """ステージのゴール駅を強制記録（取りこぼし防止）。重複なら何もしない。"""
        key = (stage.index, 1.0)
        if self._last_key == key:
            return
        self._record(stage, 1.0)

    def _record(self, stage: Stage, progress: float) -> None:
        lat = stage.start.lat + (stage.goal.lat - stage.start.lat) * progress
        lon = stage.start.lon + (stage.goal.lon - stage.start.lon) * progress
        self.points.append(TrackPoint(
            lat=lat, lon=lon,
            time=dt.datetime.now(dt.timezone.utc),
        ))
        self._last_key = (stage.index, progress)

    def write_gpx(self, dir_path: str) -> str:
        """activities/YYYYMMDD_hhmmss.gpx に書き出す。書き込んだパスを返す。"""
        os.makedirs(dir_path, exist_ok=True)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(dir_path, f"{ts}.gpx")

        out: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="路線Rider" '
            'xmlns="http://www.topografix.com/GPX/1/1">',
            '  <trk>',
            f'    <name>{escape(self.line_name)}</name>',
            '    <type>VirtualRide</type>',
            '    <trkseg>',
        ]
        for pt in self.points:
            t_str = pt.time.strftime("%Y-%m-%dT%H:%M:%SZ")
            out.append(f'      <trkpt lat="{pt.lat:.7f}" lon="{pt.lon:.7f}">')
            out.append(f'        <time>{t_str}</time>')
            out.append('      </trkpt>')
        out.extend([
            '    </trkseg>',
            '  </trk>',
            '</gpx>',
        ])
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        return path


def default_activities_dir() -> str:
    """リポジトリ直下の activities/ を返す。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "activities")
