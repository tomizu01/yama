# 路線Rider

レトロゲーム風疑似3Dレースゲーム。実際の自転車（BLE接続のスマートトレーナー/センサー）で
走った分だけゲーム内を進む。第一弾は山手線。企画書: `docs/YamanoteDaibouken.md`

## 技術スタック

- Python 3.13 / pygame / bleak
- venv: `.venv`（pygame, bleak インストール済み）

## 実行方法

```
.venv\Scripts\python.exe main.py
```

- 起動するとセットアップ画面が出る:「BLEデバイスを検索」または「デモ走行(30km/h固定)」
- 操作: マウスX座標で左右移動のみ（ポインタが自機より左なら左へ、右なら右へ）
- 開発用キー: `↑`/`↓` 巡航速度調整（デモ走行時のみ有効）、`ESC` 終了

## 進捗状況

- [x] **フェーズ1: レトロゲーム風レース** — 完了（2026-06-03）。ゲーム性検証可能な状態
- [x] **フェーズ2: BLE連携** — 完了（2026-06-03）。CSC/CPS スキャン → pygame内メニューで
  デバイス＋モード選択 → テレメトリから飽和速度算出 → 慣性シミュレーションで現在速度収束
- [ ] **フェーズ3: ステージ作成** — 山手線1駅=1ステージ、東京駅発着、ノルマタイム・勾配。
  ここで gradient を BleSpeedSource に流し込む。FE-C 送信も同時に実装する想定
- [ ] **フェーズ4: ブラッシュアップ**

BLE実機は自宅にある（仕様書は docs/ に格納済み）。

## コード構成

```
main.py                 エントリポイント
game/
  config.py             全設定値（ゲームバランス調整はここだけ触ればよい）
  projection.py         疑似3D投影 (z,u) → 画面座標。u: 道路中心=0, 道路端=±1
  assets.py             画像読込 + 藁のスケールキャッシュ
  speed_source.py       SpeedSource 抽象 / ConstantSpeedSource(デモ) / BleSpeedSource(3モード+慣性)
  menu.py               起動時セットアップ画面（スキャン→デバイス選択→モード選択）
  player.py             自転車（左右移動・描画）
  obstacles.py          藁の生成・遠近描画・衝突判定
  race.py               Race クラス（update/draw 分離）+ メインループ run()
  ble/
    constants.py        BLE UUID 定数（CSC/CPS/FE-C）
    parser.py           CSC/CPS Measurement のパース + speed/cadence 算出（ロールオーバー処理込み）
    bridge.py           bleak を専用スレッドで asyncio 駆動。queue.Queue で双方向通信
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
  optional `cadence_rpm` / `power_w` / `mode_label` / `close()`）。
  `ConstantSpeedSource`（デモ走行）と `BleSpeedSource`（BLE接続）が実装

## フェーズ2 BLE実装メモ

- **アーキテクチャ**: `game/ble/bridge.py` の `BleBridge` が専用スレッドで asyncio loop を回す。
  ゲーム側 → BLE は cmd Queue（scan/connect/disconnect/stop）、BLE → ゲームは
  `bridge.events` Queue（`BridgeEvent(kind, payload)`）。`menu.py` がメインループ中に
  drain して状態遷移、`BleSpeedSource` がレース中に drain してテレメトリ反映
- **走行モード（aicyc 由来 / 3モード）**: ユーザーが起動時メニューで選択
  - `SPEED`: ホイール回転 → 速度をそのまま使用（飽和速度=センサー速度）
  - `CADENCE`: 飽和 = `cadence/3 - g*2` (g>-1%, cadence≤30で0) / `20 + max(cad-60,0)/3 - g*2` (g≤-1%)
  - `POWER`: 飽和 = `log10(3 + max(power - g*20, 0.5)) * 15` (g>1% かつ power≤30W で0)
- **慣性シミュレーション**: `speed += (saturation - speed) * (1 - exp(-dt / τ))`、τ=4s
  （aicyc の 5Hz×0.05 と等価。`_INERTIA_TAU_S` で調整可能）
- **停止検出**: 3秒間テレメトリ無し → センサー値を0に落として飽和速度0へ
- **勾配 (gradient)**: フェーズ2では常に0で計算。フェーズ3でステージから流し込む
- **デバイス選択**: スキャン後、ユーザーが pygame メニューでクリック選択 → モード選択
  - スキャン段階では UUID フィルタしない。多くの CSC センサー（CYCPLUS C3 等）は
    広告パケットに 0x1816 を載せず、UUIDフィルタすると見えなくなるため
  - 広告UUIDから推測できるものは `[CSC]`/`[CPS]` タグを付けて上位に並べる（参考表示）
  - プロファイル判定は接続後の `client.services` から実際の GATT サービス一覧を見て決める
    （両対応なら CPS 優先）
  - Feature キャラから wheel/crank/power 対応を読み、未対応モードはメニュー上で無効化
- **タイムスタンプ解像度の罠**: CSC のホイールは 1/1024 秒、**CPS のホイールは 1/2048 秒**
  （クランクはどちらも 1/1024 秒）。`parser.py` で `ticks_per_sec` を分けている
- **詳細仕様**: docs/ の3ファイル（CSC, CPS, FE-C）参照。aicyc-CLAUDE.md は過去プロジェクト
  のリファレンス（速度計算式・慣性式の出典）
