"""ゲーム全体の設定値。

道路形状の値は bg.png の実測（tools/measure_bg.py）に基づく。
"""

# --- 画面 ---
SCREEN_W, SCREEN_H = 1504, 1034
FPS = 60

# --- 道路の形状（bg.png 実測） ---
VP_X, VP_Y = 752, 600        # 道路の消失点
ROAD_SLOPE = 2.705           # 道路半幅 = ROAD_SLOPE * (y - VP_Y) [px]

# --- プレイヤー平面（衝突判定が起きるスクリーン上の位置） ---
PLAYER_Y = 1000              # プレイヤーの足元（接地）のスクリーンY
ROAD_HALF_W = ROAD_SLOPE * (PLAYER_Y - VP_Y)  # プレイヤー平面での道路半幅 [px]

# 仕様: 最前面では道幅 = 藁4個分（プレッシャー軽減のため見た目はさらに80%に縮小）
WARA_SCALE = 0.8
WARA_FRONT_W = int(ROAD_HALF_W * 2 / 4 * WARA_SCALE)

# プレイヤーの描画サイズ（chari.png は 128x128）
PLAYER_SPRITE_W = 300

# --- 遠近投影 ---
Z_NEAR = 12.0                # 投影定数 [m]。小さいほど手前で急拡大する
Z_SPAWN = 300.0              # 障害物の出現距離 [m]
Z_DESPAWN = -5.0             # 通過後に消す距離 [m]

# --- 走行 ---
CRUISE_KMH = 30.0            # フェーズ1の巡航速度 [km/h]
VISUAL_SPEED_FACTOR = 2.0    # 見た目の進行速度の倍率（HUDの速度表示には影響しない）
                             # ※フェーズ3でステージ距離（実駅間距離）との整合を要検討
DEBUG_SPEED_STEP = 5.0       # ↑↓キーでの速度調整幅 [km/h]（開発用）

# --- 操作 ---
LATERAL_SPEED = 1.5          # 左右移動速度 [u/s]（u: 道路中心=0, 道路端=±1）
PLAYER_U_LIMIT = 0.85        # 左右移動の限界

# --- 衝突 ---
WARA_U_HALF = 0.25 * WARA_SCALE  # 藁の半幅 [u]（見た目の縮小に合わせる）
PLAYER_U_HALF = 0.10         # プレイヤーの半幅 [u]
HIT_U_DIST = (WARA_U_HALF + PLAYER_U_HALF) * 0.9   # 当たり距離（少し甘め）
HIT_SPEED_MULT = 0.35        # 衝突直後の速度倍率
HIT_RECOVERY_PER_S = 0.22    # 速度倍率の回復速度 [/s]（約3秒で全回復）

# --- 障害物の生成 ---
SPAWN_GAP_MIN = 36.0         # 障害物列の間隔 [m]
SPAWN_GAP_MAX = 64.0
LANE_SLOTS = (-0.60, -0.20, 0.20, 0.60)  # 藁を置けるレーン位置 [u]（20%内側に寄せ）
LANE_JITTER = 0.06           # レーン位置の揺らぎ [u]
MAX_WARA_PER_ROW = 2         # 1列の最大数（4レーン中2つまで → 必ず通り道が残る）
