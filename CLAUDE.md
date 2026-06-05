# 路線Rider

レトロゲーム風疑似3Dレースゲーム。実際の自転車（BLE接続のスマートトレーナー/センサー）で
走った分だけゲーム内を進む。収録路線: 山手線・京浜東北線（`lines/*.csv` で追加可能）。
企画書: `docs/YamanoteDaibouken.md`

## 技術スタック

- Python 3.13 / pygame / bleak
- venv: `.venv`（pygame, bleak インストール済み）

## 実行方法

```
.venv\Scripts\python.exe main.py
```

- 起動するとセットアップ画面:「BLEデバイスを検索」または「デモ走行(30km/h固定)」
- セットアップ後に路線選択画面（`lines/*.csv` から選択）
- ステージ開始画面→レース→クリア画面 を全駅分ループ。最終駅のクリア画面で終了
- 操作: マウスX座標で左右移動のみ（ポインタが自機より左なら左へ、右なら右へ）
- 各画面の遷移はマウスクリック。クリア画面で「GPXを記録する」ボタンを押すと
  `activities/YYYYMMDD_hhmmss.gpx` に Strava 等にアップ可能なログを保存
- ウィンドウは角ドラッグで自由にリサイズ可（中身は論理1504×1034を smoothscale）
- 開発用キー: `↑`/`↓` 巡航速度調整（デモ走行時のみ有効）、`ESC` 終了

## 進捗状況

- [x] **フェーズ1: レトロゲーム風レース** — 完了（2026-06-03）。ゲーム性検証可能な状態
- [x] **フェーズ2: BLE連携** — 完了（2026-06-03）。CSC/CPS スキャン → pygame内メニューで
  デバイス＋モード選択 → テレメトリから飽和速度算出 → 慣性シミュレーションで現在速度収束
- [x] **フェーズ3: ステージ作成** — 完了（2026-06-03）。`lines/yamanote.csv`(31駅) から
  30ステージ生成、ステージ開始/クリア画面、ノルマタイム判定（25km/h基準）、HUD拡張
- [-] **フェーズ4: ブラッシュアップ** — 着手中。勾配＋FE-C負荷制御は実装済み
  （2026-06-04、下記「フェーズ4 勾配・FE-C実装メモ」参照）。
  勾配を考慮したノルマ時間も実装済み（2026-06-05、下記参照）

### フェーズ3完了後の追加機能

- [x] GPX走行ログ記録（`game/recorder.py`）。5秒おき＋進捗チェック、
  クリア画面の「GPXを記録する」ボタンで `activities/` に出力（`<type>VirtualRide</type>`）
- [x] ウィンドウサイズ可変化（`game/display.py`）。論理1504×1034 → 自前 smoothscale
- [x] 漕ぎアニメ（2026-06-04）。chari.png / chari2.png を1/3秒毎に切替
  （`PLAYER_ANIM_INTERVAL_S`）。実質速度 ≤ 0.1km/h で静止コマに戻る
- [x] BLE自動再接続（2026-06-04）。詳細は「フェーズ2 BLE実装メモ」参照
- [x] 路線選択画面（2026-06-04）。京浜東北線追加。詳細は「路線追加メモ」参照
- [x] 実況AI向けHUD表記（2026-06-04）。レースHUD右上に
  「ステージゴールまであと X.XX km」を日本語で表示。外部の実況AI（画面キャプチャ →
  画像解析 → TTS で実況する別プロジェクト）が `DIST`/`GOAL` の数値を取り違えるため、
  どの数値が残距離かを表記で曖昧さなく示したもの

### 検証待ち（2026-06-05 時点）

- **実況AIの距離認識**（要・実況システム環境）: 「ステージゴールまであと」表記で
  誤読が減るか。まだ誤読するなら 左HUDの GOAL/DIST 行の削除 →
  それでもダメなら state.json 側道チャンネル（ゲームが毎秒状態をJSON出力し
  実況AIはOCRでなくそれを読む）の実装を検討
- **京浜東北線の実走**（ノルマ調整と合わせて）

### 将来構想（未着手・別途相談）

- **ステージ別の背景・障害物画像**（2026-06-05 言及）: ステージによって
  背景画像（bg.png）と障害物画像（wara.png）を切り替える機能。
  画像素材の用意が必要なため、着手時にユーザーと相談してから進めること。
  実装時の注意: 背景を変える場合、道路形状（消失点・道路半幅）は
  `tools/measure_bg.py` で再測定して config に反映する必要がある

### 実走検証（2026-06-04 完了）

山手線一周（30ステージ）を実機トレーナーで完走し、全要素を検証済み:

- **BLE**: 安定動作（自動再接続実装後）
- **ゲームバランス**: 「藁をちゃんとよけないとノルマに届かない」狙い通りの難易度と
  ユーザー評価。バランス定数（ノルマ25km/h・衝突ペナルティ等）は完成状態 →
  **安易に変えないこと**
- **漕ぎアニメ**: レトロゲーム風として上出来との評価
- **GPX**: Strava にアップ成功。セグメント重複も無く問題なし

（センサー: CSC: CYCPLUS C3 / CPS: Think Rider、ケイデンスモードで動作確認）

### FE-C 負荷制御の実機検証（2026-06-05 完了）

Think Rider 実機で FE-C 制御を有効にして検証済み:

- **勾配→負荷反映**: 動作確認。+2% でも少しペダルが重くなり、-2% では体感的に
  明確に軽くなる（登りより下りのほうが体感差が大きい）
- 負荷の体感を強めたい場合は `bridge._build_fec_track_resistance()` で送信する
  Grade に倍率を掛ける手もあるが、現状は実勾配をそのまま送る方針

## コード構成

```
main.py                 エントリポイント
game/
  config.py             全設定値（ゲームバランス調整はここだけ触ればよい）
  projection.py         疑似3D投影 (z,u) → 画面座標。u: 道路中心=0, 道路端=±1
  assets.py             画像読込 + 藁のスケールキャッシュ
  speed_source.py       SpeedSource 抽象 / ConstantSpeedSource(デモ) / BleSpeedSource(3モード+慣性)
  menu.py               起動時セットアップ画面（スキャン→デバイス選択→モード選択→FE-C選択）+ 路線選択画面
  player.py             自転車（左右移動・漕ぎアニメ・描画）
  obstacles.py          藁の生成・遠近描画・衝突判定
  race.py               Race クラス（update/draw 分離）+ ステージ進行ループ run()
  stages.py             駅CSV読込 / Station・Stage / 距離概算 / ノルマ計算
  recorder.py           GPXトラック記録（線形補完で lat/lon を5秒おきに）
  display.py            ウィンドウサイズ可変化（論理1504×1034 → 自前で smoothscale-blit）
  ble/
    constants.py        BLE UUID 定数（CSC/CPS/FE-C）
    parser.py           CSC/CPS Measurement のパース + speed/cadence 算出（ロールオーバー処理込み）
    bridge.py           bleak を専用スレッドで asyncio 駆動。queue.Queue で双方向通信
tools/
  measure_bg.py         bg.png の道路形状測定（開発用）
  screenshot_test.py    ヘッドレスで数秒シミュレートしてスクショ保存（描画検証用）
  perf_test.py          フレーム時間計測（Race の update+draw のみ、display抜き）
  gradient_test.py      勾配/FE-C の検証（CSV読込・Page51エンコード・HUD描画）
  line_select_test.py   路線選択の検証（一覧・両CSV・バリデーション・画面描画）
  norma_gradient_test.py 勾配ノルマ補正の検証（倍率クランプ・全路線CSV）
docs/
  YamanoteDaibouken.md  企画書
  ble-csc-profile.md    BLE: Cycling Speed and Cadence 仕様
  ble-cps-profile.md    BLE: Cycling Power 仕様
  tacx-fec-over-ble.md  BLE: FE-C over BLE 仕様（トレーナー制御・双方向）
lines/
  yamanote.csv          山手線: 駅名,緯度,経度,勾配[%]（末尾に東京駅を再掲し周回を閉じる）
  keihin_tohoku.csv     京浜東北線: 大宮→大船 46ステージ（直線路線、周回なし）
  keihin_tohoku_north.csv 京浜東北線（北）: 21ステージ（ショートコース）
  keihin_tohoku_south.csv 京浜東北線（南）: 25ステージ（ショートコース）
activities/             走行ログ（GPX）の出力先。gitignore（ユーザー生成物）
sozai/images/           bg.png(1504x1034) / chari.png・chari2.png(128x128, 漕ぎアニメ2コマ) / wara.png(96x96)
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
  HUDの速度表示は実速度のまま。`Race` 内で `distance_m`（視覚距離・障害物用、×2倍）と
  `real_distance_m`（実距離・ステージ進行/HUD用）を分離してこの矛盾を解消している
- **`PERSPECTIVE_POWER = 2.2`**: 投影曲線のベキ乗（`t = (Z_NEAR/(Z_NEAR+z))^k`）。
  >1で遠くは控えめ・手前で一気に迫る加速感。ユーザー調整で2.2に確定
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
- **自動再接続（2026-06-04）**: 確立済み接続が不意に切れたら bridge が同アドレスへ
  無限リトライ（3秒間隔）。意図的切断（disconnect/close/別デバイスへの connect）では
  リトライしない（`_reconnect_address` / `_expect_disconnect` フラグで区別）。
  保険として `BleSpeedSource` に20秒テレメトリ途絶ウォッチドッグ（切断 callback が
  来ないまま接続が死ぬケース → `bridge.request_reconnect()` で強制再接続）。
  切断〜復帰までレースHUDに「BLE RECONNECT...」を点滅表示
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

## フェーズ4 勾配・FE-C実装メモ（2026-06-04）

- **勾配データ**: `lines/yamanote.csv` の第4カラム（% 単位、省略時0）。
  各ステージの勾配は「**到着駅**」の値を使う（例: 東京→有楽町は有楽町の勾配で走る）。
  `Stage.gradient_pct` プロパティ = `goal.gradient_pct`。ステージ中はずっと同じ勾配
- **勾配の流し込み**: `race.run()` がレース開始時に `speed_source.set_gradient()` を呼ぶ
  （`SpeedSource` 基底に no-op の `set_gradient()` あり、デモ走行でも安全）。
  BLE の CADENCE/POWER モードでは飽和速度式の `g` に効く（式は既存、フェーズ2から待機済み）
- **FE-C 負荷制御**: モード選択後、接続デバイスが FE-C サービス
  (`6E40FEC1-...`) を持つ場合のみ「FE-C制御 ON/OFF」選択画面を表示（`_S_FEC_SELECT`）。
  ON なら `BleSpeedSource(fec_enabled=True)` が勾配を Page 51 (Track Resistance) で
  トレーナーへ送信。HUD の MODE 表示に「+FEC」が付く
- **定期再送**: トレーナー側タイムアウトでの負荷解除・再接続後の負荷消失に備えて
  `BleSpeedSource` が 2 秒おきに同じ勾配を再送（`_FEC_RESEND_INTERVAL_S`）。
  ステージ開始時は即時送信。bridge 側は未接続/非対応なら黙って無視（書込失敗もログのみ）
- **エンコード**: `bridge._build_fec_track_resistance()`。13バイト ANT メッセージ
  (sync 0xA4 / broadcast 0x4E / ch 5)、Grade = `(g% + 200) / 0.01` Uint16 LE、
  CRR = 0.004（アスファルト）。docs/tacx-fec-over-ble.md の例と照合済み（tools/gradient_test.py）
- **HUD**: レース中に `GRADE +5.0 %` 行（登り=橙、下り=水色）。ステージ開始画面にも勾配表示
- **勾配ノルマ補正（2026-06-05）**: 勾配 +1% につきノルマ時間 +10%（上限 +200%=3倍）、
  -1% につき -10%（下限 -50%=半分）。`stages.norma_gradient_factor()` で倍率を計算し
  `build_stages()` で `norma_s` に乗算（参照は全て `stage.norma_s` 経由なので一箇所で完結）。
  ステージ開始画面の「(25 km/h)」表記は補正後の実効ペースに変更。
  検証: `tools/norma_gradient_test.py`（クランプ・全路線CSV）

## 路線追加メモ（2026-06-04）

- **路線選択画面**: セットアップ後・ステージ開始前に `menu.run_line_select()` を表示。
  `stages.available_lines()` が `lines/*.csv` を列挙し、表示名は
  `stages.LINE_DISPLAY_NAMES`（dict の順序 = 画面の並び順）。未登録 CSV はファイル名で
  末尾に出る。サブラベルに 起点→終点 / ステージ数 / 総距離 を表示
- **路線の追加方法**: `lines/<key>.csv`（駅名,緯度,経度,勾配[%]）を置き、
  `LINE_DISPLAY_NAMES` に表示名を1行足すだけ。周回路線は末尾に1駅目を再掲、
  直線路線はそのまま（連続ペア enumerate なので両対応）
- **勾配バリデーション**: |勾配| > 30% は `load_stations` が ValueError
  （緯度経度の重複カラム混入などのデータミス検出。実際に京浜東北線の初版CSVで
  「駅名,緯度,経度,緯度,経度,勾配」の6列混入があり、これを機に追加）。
  読込エラーの路線は選択画面でグレーアウト＋エラー表示され、ゲームは落ちない
- **GPX**: `TrackRecorder(line_name=選択路線名)` で記録される

## フェーズ3 ステージ実装メモ

- **駅データ**: `lines/yamanote.csv`（駅名,緯度,経度,勾配[%]）。末尾に1駅目（東京）を再掲して
  周回を閉じる。連続ペアを enumerate するだけで N ステージ生成
- **距離概算**: 緯度1度≒111km、経度1度≒91km（東京緯度 cos(35°)×111km）。
  山手線一周は概算 32.6km（実 34.5km、誤差 5% 程度で「概算でOK」要件を満たす）
- **ノルマ**: 25 km/h で走行したときの所要時間（`stages.NORMA_KMH`）。
  2026-06-05 から勾配補正あり（「フェーズ4 勾配・FE-C実装メモ」参照）
- **ステージ進行**: `race.run()` が「開始画面 → レース → クリア画面」を 30 回ループ。
  クリア画面で経過時間 ≤ ノルマで WIN、超過で LOSE 表示。最終ステージのクリア画面で
  クリックすると終了
- **距離の2系統**: `Race.distance_m` は ×`VISUAL_SPEED_FACTOR` の視覚距離（障害物の
  生成位置に使う）、`Race.real_distance_m` は実距離（ステージゴール判定・HUD表示に使う）
- **ステージ間の SpeedSource**: 同じ `speed_source` を全ステージで共有。BLE 接続も
  画面遷移中の `_wait_click_or_quit` 内で update() され続けるので、停止検出・テレメトリ
  受信は途切れない
- **GPX記録**: `TrackRecorder` がセッション全体（全ステージ）の点を蓄積。Race.update から
  5秒おきに進捗チェック → 開始駅↔終了駅を progress(0..1) で線形補完した (lat, lon, UTC時刻)
  を記録。ステージクリア時にゴール駅を `force_record_endpoint` で強制記録（取りこぼし防止）。
  クリア画面の「GPXを記録する」ボタンで `activities/YYYYMMDD_hhmmss.gpx` に書き出す
  （`<type>VirtualRide</type>` 入り GPX 1.1）
