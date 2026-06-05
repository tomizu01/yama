"""勾配によるノルマ時間補正の検証（2026-06-05）。

- norma_gradient_factor() のクランプ動作（+1%→+10%、最大3倍 / -1%→-10%、最小半分）
- 全路線 CSV を読み込み、勾配のあるステージで norma_s に倍率が掛かっていること
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import stages as S


def test_factor() -> None:
    cases = {
        0.0: 1.0, 1.0: 1.1, 2.0: 1.2, 5.0: 1.5,
        20.0: 3.0, 25.0: 3.0,        # 上限 +200%（3倍）
        -1.0: 0.9, -2.0: 0.8, -5.0: 0.5,
        -6.0: 0.5, -10.0: 0.5,       # 下限 -50%（半分）
    }
    for g, expect in cases.items():
        got = S.norma_gradient_factor(g)
        assert abs(got - expect) < 1e-9, f"g={g}: expected {expect}, got {got}"
        print(f"  g={g:+6.1f}% -> factor {got:.2f}  OK")


def test_lines() -> None:
    for line in S.available_lines():
        stations = S.load_stations(line.csv_path)
        stgs = S.build_stages(stations)
        print(f"--- {line.name} ({len(stgs)} stages)")
        for st in stgs:
            base = st.distance_m / (S.NORMA_KMH / 3.6)
            expect = base * S.norma_gradient_factor(st.gradient_pct)
            assert abs(st.norma_s - expect) < 1e-6, st.label
            if abs(st.gradient_pct) >= 2.0:
                print(f"  {st.label}: {st.distance_m:.0f}m"
                      f" g={st.gradient_pct:+.1f}%"
                      f" norma {S.format_mmss(base)} -> {S.format_mmss(st.norma_s)}")


if __name__ == "__main__":
    print("[factor]")
    test_factor()
    print("[lines]")
    test_lines()
    print("ALL OK")
