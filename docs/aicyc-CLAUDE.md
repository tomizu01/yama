# AI Cyc - Virtual Cycling App

## Overview
GPXルート上をBLEデバイス（サイクルコンピュータ/パワーメーター/スマートトレーナー）で走行するバーチャルサイクリングWebアプリ。走行中はAIキャラクター（こはる/ひな）が周辺スポット情報や走行状態をもとに会話してくれる。ライド開始前にパートナーキャラクターを選択可能。

## Tech Stack
- **Framework**: Next.js 16 (App Router, TypeScript, Tailwind CSS v4)
- **Map**: Leaflet（国土地理院標準タイル `https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png`）
- **GPX Parser**: @tmcw/togeojson
- **BLE**: Web Bluetooth API（対象ブラウザ: Chrome Desktop）
- **TTS**: VOICEVOX（さくらAI Engine）/ ElevenLabs（`eleven_v3` Alpha + stability=1.0 Robust）— サイドバーで切替可能
- **外部API**:
  - Google Places API (New) — 周辺スポット検索
  - Gemini API (`gemini-3.1-pro-preview`) — キャラ会話生成。reasoning モデルで thinking tokens 消費、`thinkingLevel: 'low'` + `maxOutputTokens: 8192` 設定
  - ElevenLabs TTS API — 高品質音声合成（Creatorプラン）
  - OpenAI Embeddings API (`text-embedding-3-small`, 1536次元) — チャットメッセージのベクトル化（RAG用）
- **DB**: PostgreSQL 15 + pgvector 0.8.0 (`aicyc` データベース、`aicyc`ユーザー、127.0.0.1:5432)
  - 旧: MySQL（`/var/www/kpi/config/database.php`）— RAG実装に伴いPostgreSQLへ移行済み
  - `chat_messages` テーブルにメッセージ本文＋embeddingを保存、pgvector `<=>` 演算子で類似検索

## Project Structure
```
src/
├── app/
│   ├── page.tsx           # メインページ（状態管理・走行ロジック・記録・AIメッセージ統合）
│   ├── layout.tsx
│   ├── globals.css
│   └── api/
│       ├── chat/route.ts             # POST /api/chat — チャットをDB保存。role=aiならOpenAI embedding取得して保存
│       ├── similar-messages/route.ts # POST /api/similar-messages — 参照メッセージをembedding化→pgvectorで過去ライドの類似AI発言を検索
│       ├── places/route.ts           # POST /api/places — Google Places API (New) プロキシ
│       ├── voicevox/route.ts         # POST /api/voicevox — さくらAI Engine TTSプロキシ（WAV返却）
│       └── elevenlabs/route.ts       # POST /api/elevenlabs — ElevenLabs TTSプロキシ（MP3返却）
├── components/
│   ├── MapView.tsx        # Leaflet地図（GSIタイル、ルート描画、現在位置追従、ズーム±ボタン）
│   ├── DeviceSetup.tsx    # BLEデバイス選択UI（種類→接続→データモード 3ステップ）
│   ├── GpxUploader.tsx    # GPXファイルアップロード
│   ├── RideHUD.tsx        # 走行HUD（速度/ケイデンス/パワー/勾配/距離/時間）
│   ├── ChatBubble.tsx     # AIキャラのチャット吹き出し（タイプライター + 表情スプライト + ユーザー入力欄）
│   └── UserNameEditor.tsx # ユーザー名表示 + 鉛筆アイコンでモーダル編集
├── lib/
│   ├── ble/
│   │   ├── types.ts       # 型定義・UUID定数・変換係数
│   │   ├── csc.ts         # CSC (0x1816) — ホイール/クランク回転→速度/ケイデンス
│   │   ├── cps.ts         # CPS (0x1818) — パワー+ホイール/クランク（タイムスタンプ1/2048s注意）
│   │   ├── fec.ts         # FE-C over BLE — 勾配送信(Page 51)/ERG(Page 49)/抵抗(Page 48)
│   │   └── index.ts
│   ├── gpx/
│   │   └── index.ts       # GPXパース/距離計算(Haversine)/位置補間/勾配算出/獲得標高/GPX生成
│   ├── overpass.ts        # Google Places API (New) で周辺スポット取得（ファイル名は歴史的経緯で維持）
│   ├── characters.ts      # キャラクター定義（こはる/ひな）— プロンプト・atlas画像・フォールバック・TTS voice ID等
│   ├── gemini.ts          # Gemini API — start/goal + ChatMode (dialog/dialog_engaged/spot) でプロンプト切替
│   ├── openai.ts          # OpenAI API client — getEmbedding() (text-embedding-3-small) / toPgVector()
│   ├── voicevox.ts        # TTS client — fetchSpeechAudio()/loadAudio()/playSpeechAudio()/stopSpeech()
│   └── db.ts              # pg プール — PostgreSQL 127.0.0.1:5432/aicyc（aicyc/aicyc）
├── types/
│   └── web-bluetooth.d.ts # Web Bluetooth API型定義
public/
├── koharu.png             # キャラ画像（旧・未使用）
├── koharu_atlas.png       # こはる表情アトラス 1600x450 (400x450 × 4フレーム)
└── hina_atlas.png         # ひな表情アトラス 1600x450 (400x450 × 4フレーム、こはると同仕様)
docs/
├── ble-csc-profile.md     # CSCプロファイル仕様
├── ble-cps-profile.md     # CPSプロファイル仕様
└── tacx-fec-over-ble.md   # Tacx FE-C over BLE仕様
```

## Commands
```bash
npm run dev       # 開発サーバー (port 2000)
npm run build     # 本番ビルド
npm run start     # 本番サーバー (port 2000)
npm run lint      # ESLint
```

## Environment Variables
`.env.local` に下記を定義（gitignore済み）:
```
NEXT_PUBLIC_GEMINI_API_KEY=<Gemini API key>
SAKURA_AI_TOKEN=<さくらAI Engine token>
GOOGLE_PLACES_API_KEY=<Google Places API key>
ELEVENLABS_API_KEY=<ElevenLabs API key>
OPENAI_API_KEY=<OpenAI API key>  # embedding用（server-side only、NEXT_PUBLIC_ 無し）
```
※ `NEXT_PUBLIC_` prefix のため現状クライアントバンドルに含まれる。公開運用時はAPI Route経由に変更すること。

## Deployment
- ALB経由でSSL終端、ドメイン: `aicyc.mediowl.ai`
- `next.config.ts` に `allowedDevOrigins` 設定済み
- 本番モード（build + start）推奨（devモードだとALBがWebSocket/HMRを通さずエラーになる）

## PostgreSQL + pgvector セットアップ（Amazon Linux 2023）
再構築時の手順:
```bash
# 1. パッケージインストール
sudo dnf install -y postgresql15-server postgresql15-contrib postgresql15-server-devel gcc make git

# 2. DB初期化 & 起動
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql

# 3. pgvector をソースビルド（AL2023リポジトリには無いため）
cd /tmp && git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd /tmp/pgvector && make && sudo make install

# 4. DB/ユーザー作成 + 拡張有効化
sudo -u postgres psql <<'SQL'
CREATE DATABASE aicyc;
CREATE USER aicyc WITH PASSWORD 'aicyc';
ALTER DATABASE aicyc OWNER TO aicyc;
GRANT ALL PRIVILEGES ON DATABASE aicyc TO aicyc;
SQL
sudo -u postgres psql -d aicyc -c "CREATE EXTENSION vector;"

# 5. pg_hba.conf でlocalhost接続をmd5認証に変更
sudo sed -i 's|127.0.0.1/32            ident|127.0.0.1/32            md5|' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl reload postgresql
```
- 接続情報: `127.0.0.1:5432` / user=`aicyc` / password=`aicyc` / db=`aicyc`（`lib/db.ts` にハードコード、必要なら .env 化）

## BLE Device Support
- **CSC (0x1816)**: Speed/Cadence センサー
- **CPS (0x1818)**: パワーメーター/スマートトレーナー
- **FE-C over BLE**: Tacxトレーナー勾配制御（CPS/CSCデバイスがFE-Cも公開している場合に自動検出）

## Data Modes（慣性シミュレーション）
各モードで「飽和速度」（現在の入力を続けた場合に収束する速度）を算出し、現在速度は更新ごとに `現在速度 += (飽和速度 - 現在速度) × 0.05` で緩やかに変化する（200ms×5%≒数秒で収束）。

| モード | 飽和速度の算出 |
|--------|---------------|
| speed | センサーから取得したスピードをそのまま使用 |
| cadence | 勾配 > -1%: `cadence / 3 - gradient × 2`（ただしcadence ≤ 30で飽和速度0） / 勾配 ≤ -1%: `20 + max(cadence - 60, 0) / 3 - gradient × 2`（下り坂はペダルなしでも進む） |
| power | 勾配 > 1% かつ power ≤ 30W: 飽和速度0 / それ以外: `log10(3 + max(power - gradient × 20, 0.5)) × 15` |

## AI Chat (キャラクターシステム)
画面上部にチャットエリアを配置。右側にキャラ、左側に吹き出し + ユーザー入力欄（吹き出しと同幅で下段）。

### キャラクター選択
- ライド開始前にサイドバーの「パートナー選択」UIでキャラクターを選択
- 選択肢: **こはる**（癒し系・ポンコツ天然）/ **ひな**（甘えん坊・しっかり者の妹系）
- キャラ定義は `lib/characters.ts` に一元管理（`CharacterId` 型: `'koharu' | 'hina'`）
- 各キャラごとにプロンプト（personaBlock）、atlas画像パス、フォールバックメッセージ、VOICEVOX speakerId、ElevenLabs voiceIdを持つ
- ライド開始時に `characterRef` にスナップショットし、ライド中は固定
- Gemini API の3関数（start/riding/goal）すべてに `characterId` を渡してキャラ別プロンプトで生成

### 表情システム
`koharu_atlas.png` (1600x450、4フレーム横並び) からCSS `background-position` で1フレームだけ表示。切替は瞬時（トランジションなし）。
| index | 表情 | 切替条件 |
|-------|------|---------|
| 0 | 通常 (normal) | 勾配 \|g\| ≤ 1% |
| 1 | 楽 (easy) | 勾配 < -1%（下り） |
| 2 | 苦 (pain) | 勾配 > +1%（登り） |
| 3 | 不機嫌 (grumpy) | （予約）将来ユーザーのチャット入力で不適切発言を検知した時に使用 |

### チャットループ（テキスト＋音声同期）
ライド開始時に async ループが起動し、テキスト表示と音声再生を同期制御する。

**走行中ループ:**
1. ユーザー発言タイミングを見てチャットモードを判定（初回は `generateStartMessage()` のみ）
   - `spot`          : 直近60秒以内にユーザー発言がない → Google Places APIで近隣スポット取得し話題生成
   - `dialog`        : 直近60秒以内にユーザー発言あり → 直近6メッセージを「あなた：/ユーザー：」形式で渡し会話継続
   - `dialog_engaged`: `dialog` が120秒以上継続 → 上記 + 直近3件のAI発言を結合してRAG検索し類似会話2件を追加
2. Gemini API で `generateCharacterMessage(mode, opts)` 呼び出し
3. ボイスONなら `fetchSpeechAudio()` → `loadAudio()` で音声データ取得＋デコード
4. `setChatMessage()` と `playSpeechAudio(audio, url, 20000)` を同時に開始 — タイプライター演出と音声再生が同期。音声再生は20秒で強制終了（TTSハルシネーション対策）
5. 両方の完了を `Promise.all` で待機（`onTypewriterDone` コールバック + `audio.onended`/20秒タイムアウト）
6. ライド終了済みならゴール処理へ。継続中なら自動音声入力ONの場合は `chatBubbleRef.startListening()` で音声認識を開始し、5秒間待機（`interruptibleSleep`）してから次ループ

**チャットモード判定用のref:**
- `lastUserMessageAtRef`       : 最新のユーザー発言時刻
- `userEngagementStartAtRef`   : 現在のエンゲージメント開始時刻（60秒以上の沈黙で再設定）

**ライド終了時:**
- 走行ループ（200ms interval）が `isFinishedRef = true` を立て、`wakeupChatLoop()` でsleepを即解除
- チャットループの次イテレーションで `generateGoalMessage()` → 音声生成 → テキスト＋音声同時再生 → ループ終了

**ユーザーメッセージ:**
- `handleUserMessage` が `lastUserMessageAtRef`/`userEngagementStartAtRef` を更新し、履歴にも保存
- 60秒以上のサイレンスがあった場合は engagement 開始時刻をリセット（Mode B判定のため）
- 次のループイテレーションでチャットモード判定に反映される

### プロンプト共通事項
- 各生成関数に `userName` 引数を渡し、プロンプト内に「あなたが、ユーザーを呼ぶ呼称は、○○さんで統一してください」を注入
- `situationStart/Riding/Goal` は `characters.ts` 側で管理、キャラごとに持つ
- 会話履歴の注入フォーマット:
  - `dialog` / `dialog_engaged`: 直近6件を「あなた：／ユーザー：」形式で（`formatChatHistoryAsDialog`）
  - `goal`: 直近10件を「- チャット書き込み内容: ... / 書き込んだ人: role」形式（`formatChatHistory`）
  - `spot` / `start`: 履歴なし
- 文字数上限: 全メッセージ（走行中/開始時/ゴール時）とも最大50文字（`characters.ts` の `situationRiding/Start/Goal` で設定）
- ハルシネーション対策として50文字制限を維持（ElevenLabs v3は長文ほどハルシネーションしやすい傾向）

### 表示アニメーション
- タイプライター演出: 143ms間隔(約7cps)で1文字ずつ表示
- `Array.from()` でサロゲートペア（絵文字等）対応
- タイプライター完了時に `onTypewriterDone` コールバックでチャットループに通知

### チャット永続化＆RAG
- テーブル `public.chat_messages`（PostgreSQL + pgvector）
  ```
  id            BIGSERIAL PRIMARY KEY
  user_id       VARCHAR(64) NOT NULL DEFAULT 'default'   -- 現状は固定値
  ride_id       VARCHAR(64) NOT NULL                      -- ライド毎のUUID
  character_id  VARCHAR(16) NOT NULL DEFAULT 'koharu'     -- 'koharu' | 'hina' (CHECK制約)
  role          VARCHAR(8)  NOT NULL                      -- 'user' | 'ai' (CHECK制約)
  message       TEXT        NOT NULL
  embedding     vector(1536)                              -- OpenAI text-embedding-3-small、NULL可
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  ```
  - インデックス: `(ride_id, created_at)`, `(user_id, created_at)`
  - RAG検索の量が増えたら `USING hnsw (embedding vector_cosine_ops)` の追加を検討
- ライド開始毎に `crypto.randomUUID()` で新しい `ride_id` を発行
- `saveChat()` は in-memory 履歴（`chatHistoryRef`、100件cap）と `POST /api/chat` の両方を更新
- `/api/chat` は `role=ai` のときのみ `getEmbedding()` で OpenAI API を呼び、失敗時は embedding=NULL で保存継続
- `/api/similar-messages` は参照テキスト（複数の場合は `\n` 結合して渡す）を embedding化 → pgvector `<=>` (cosine距離) で `user_id / role='ai' / character_id一致 / ride_id <> 現ライド / embedding IS NOT NULL` を上位 N件（デフォルト2件）取得

### 音声合成（TTS）
- **エンジン切替**: サイドバーの音声読み上げON時に「VOICEVOX / ElevenLabs」ボタンで切替可能。選択は `localStorage.aicyc.ttsEngine` に永続化
- **VOICEVOX**: さくらAI Engine経由。2ステップ（audio_query → synthesis）でWAV返却。`/api/voicevox`
- **ElevenLabs**: `eleven_v3` (Alpha) + `voice_settings: { stability: 1.0 (=Robust), similarity_boost: 0.75, style: 0.0, use_speaker_boost: true }`。MP3返却。`/api/elevenlabs`
  - v3のstability=1.0 Robust モードはハルシネーションを大幅に抑制（未指定時は100文字で5MB≈650秒を生成した実例あり）
  - それでも稀に発生するため、`playSpeechAudio(audio, url, 20000)` で**20秒タイムアウト強制停止**を実装
  - 長文ほどハルシネーションしやすい傾向があるため、全メッセージを50文字上限に制限
- `lib/voicevox.ts` は3ステップ: `fetchSpeechAudio()`（API呼び出し）→ `loadAudio()`（ブラウザデコード待ち）→ `playSpeechAudio(audio, url, maxDurationMs?)`（再生＋完了Promise／`maxDurationMs`で強制停止）
- 各キャラのボイス設定は `characters.ts` に集約（`voicevoxSpeakerId` / `elevenlabsVoiceId`）

| キャラ | VOICEVOX | ElevenLabs |
|--------|----------|------------|
| こはる | 107（東北ずん子 ノーマル） | `hMK7c1GPJmptCzI4bQIu` |
| ひな | 8（春日部つむぎ ノーマル） | `lhTvHflPVOqgSWyuWQry` |

### 音声入力
- Web Speech API（`SpeechRecognition` / `webkitSpeechRecognition`）を使用、言語は `ja-JP`
- 入力欄右のマイクボタンで開始/停止。録音中はボタンが赤くパルスアニメーション、プレースホルダーが「聞いています...」に変化
- `interimResults: true` でリアルタイムに暫定テキストを入力欄に表示
- 認識終了時（`onend`）に確定テキストを自動送信（`onSendMessage`）
- ライド中のみ有効。非対応ブラウザではマイクボタン非表示
- **自動音声入力**: マイクボタン右の「自動」ボタンでON/OFF切替（デフォルトOFF）。ONにすると、AIの発話完了後に自動で音声認識を開始し、5秒の待機中にユーザーが話しかけられる。`ChatBubble` が `forwardRef` + `useImperativeHandle` で `startListening()` / `autoVoiceInput` を親に公開し、チャットループから呼び出す

### ユーザー名
- サイドバー左上に `UserNameEditor`（ユーザー名表示 + 鉛筆ボタン）
- デフォルト `ユーザー`。`localStorage.aicyc.userName` に永続化
- 非同期コールバック内では `userNameRef.current` を参照（再レンダー非同期の古い値を避ける）

## ライド記録 & GPXダウンロード
- ライド開始時に `recordedPointsRef` をリセット、5秒間隔で `{lat, lng, ele, time}` を in-memory 配列に蓄積
- ライド停止/完了で `hasRecording` が true になり「GPXダウンロード」ボタン表示
- `buildGpx()` で GPX 1.1 形式にシリアライズ。**`lngOffset: +2` で全点の経度をシフト** — Strava等に上げた際の経路重複による不正記録判定を回避する目的
- ファイル名: `aicyc-{開始時刻ISO}.gpx`
- ブラウザ制約上、任意のFSに追記はできないためメモリ方式。ブラウザクラッシュで記録消失する点に注意（要なら IndexedDB に切替）

## デバッグ機能
- **デモ走行ボタン**: BLEデバイスなしで 25km/h 固定速度で自動走行（GPX読込後に表示）

## Key Implementation Notes
- CPS のホイールタイムスタンプは 1/2048s 解像度（CSCは1/1024s）— 間違えると速度が2倍ズレる
- 停止検出: 3秒間データ更新なしで速度0
- 走行ループ: 200ms間隔(5Hz)でBLEデータから位置更新
- 勾配: 現在位置から前方50mの標高差で算出、FE-Cデバイスに自動送信
- ロールオーバー処理: ホイール32bit、クランク/タイム16bit
- ref/stateの使い分け: 走行ループ内の参照値は `*Ref` (rideDataRef, currentPositionRef, currentGradeRef, distanceRef, userNameRef)、UIに出す値は別途state。Geminiなど非同期コールバックは常に最新値をrefから読む
- ゴール後処理: 走行ループが `isFinishedRef = true` → `wakeupChatLoop()` でsleep中断。チャットループは各async区切りで `isFinishedRef`/`chatLoopRunningRef` をチェックし、不要な処理をスキップしてゴールメッセージ生成に遷移
