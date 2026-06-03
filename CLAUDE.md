# 山手線大冒険 (Yamanote Daibouken)

レトロゲーム風疑似3Dレースゲーム。実際の自転車（BLE接続のスマートトレーナー/センサー）で
走った分だけゲーム内を進む。企画書: `docs/YamanoteDaibouken.md`

## 技術スタック

- Python 3.13 / pygame / bleak
- venv: `.venv`（pygame, bleak インストール済み）

## 実行方法

```
.venv\Scripts\python.exe main.py
```

- 操作: マウスX座標で左右移動のみ（ポインタが自機より左なら左へ、右なら右へ）
- 開発用キー: `↑`/`↓` 巡航速度調整（BLE導入までの仮機能）、`ESC` 終了

## 進捗状況

- [x] **フェーズ1: レトロゲーム風レース** — 完了（2026-06-03）。ゲーム性検証可能な状態
- [ ] **フェーズ2: BLE連携** — 次にやる。方式選択（CSC / CPS+FE-C）→ スキャン → ユーザー確認後に接続 → 実速度反映
- [ ] **フェーズ3: ステージ作成** — 山手線1駅=1ステージ、東京駅発着、ノルマタイム・勾配
- [ ] **フェーズ4: ブラッシュアップ**

BLE実機は自宅にある（仕様書は調査済みで docs/ に格納済み）。

## コード構成

```
main.py                 エントリポイント
game/
  config.py             全設定値（ゲームバランス調整はここだけ触ればよい）
  projection.py         疑似3D投影 (z,u) → 画面座標。u: 道路中心=0, 道路端=±1
  assets.py             画像読込 + 藁のスケールキャッシュ
  speed_source.py       速度入力の抽象化。フェーズ2でBLE実装をここに追加する
  player.py             自転車（左右移動・描画）
  obstacles.py          藁の生成・遠近描画・衝突判定
  race.py               Race クラス（update/draw 分離）+ メインループ run()
tools/
  measure_bg.py         bg.png の道路形状測定（開発用）
  screenshot_test.py    ヘッドレスで数秒シミュレートしてスクショ保存（描画検証用）
  perf_test.py          フレーム時間計測（現状 1.5ms/frame、60fps余裕）
docs/
  YamanoteDaibouken.md  企画書
  ble-csc-profile.md    BLE: Cycling Speed and Cadence 仕様
  ble-cps-profile.md    BLE: Cycling Power 仕様
  tacx-fec-over-ble.md  BLE: FE-C over BLE 仕様（トレーナー制御・双方向）
sozai/images/           bg.png(1504x1034) / chari.png(128x128) / wara.png(96x96)
```

## 重要な設計事項・実測値

- **道路形状（bg.png 実測）**: 消失点 (752,600)、道路半幅 = 2.705 × (y−600) px。
  `tools/measure_bg.py` で測定した値が `config.py` に固定されている
- **投影**: `t = Z_NEAR / (Z_NEAR + z)` で z[m] → スケール。プレイヤー平面は
  スクリーンY=1000 (`PLAYER_Y`)。藁は z<0 でも -2m まで描画して画面下へ滑り抜けさせる
- **藁のサイズ**: 仕様「道幅=藁4個分」基準 × `WARA_SCALE=0.8`（ユーザー調整。
  プレッシャー軽減のため縮小、当たり判定も連動）。レーンは `±0.60, ±0.20` の4スロット、
  1列最大2個 → 必ず通り道が残る
- **`VISUAL_SPEED_FACTOR = 2.0`**: 見た目の進行は実速度の2倍（ユーザー調整）。
  HUDの速度表示は実速度のまま。⚠ フェーズ3で実駅間距離と整合を取るとき要検討
  （実走距離はゲーム内距離の半分になる → ノルマタイムで調整 or ステージ距離2倍）
- **衝突ペナルティ**: 速度倍率 0.35 に低下 → 0.22/s で回復（約3秒）。同じ藁に再ヒットなし
- **速度入力の抽象化**: `SpeedSource` インターフェース（`update(dt)` / `speed_kmh` /
  `close()`）。フェーズ2では BLE 実装（別スレッド asyncio + queue 渡し）を追加し、
  `ConstantSpeedSource` と差し替える設計

## フェーズ2 実装メモ（着手時に参照）

- bleak は asyncio ベース。pygame と混ぜるため **BLE専用スレッドで asyncio ループを回し、
  `queue.Queue` でテレメトリをゲーム側へ渡す**（合意済みの方針)
- 方式は2パターンをユーザーが開始時に選択:
  1. CSC のみ（負荷無視）— 累積ホイール回転数の差分から速度算出（ロールオーバー注意、
     タイムスタンプは 1/1024 秒単位）
  2. CPS + （対応デバイスなら）FE-C over BLE（負荷考慮、ゲーム内勾配をトレーナーへ送信可能）
- デバイスはスキャン後、**ユーザーが確認してから接続**する（勝手に接続しない）
- 詳細仕様は docs/ の3ファイルを必ず参照すること
