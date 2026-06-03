# Tacx FE-C over BLE プロトコル仕様

ANT+ FE-C (Fitness Equipment Control) を BLE 上にトンネリングした Tacx 独自プロトコル。
FTMS (0x1826) が標準化される前に Tacx が採用した方式で、現在もレガシーモデルで使用されている。

## 概要

- Nordic UART Service (NUS) の UUID パターン `6E40xxxx-B5A3-F393-E0A9-E50E24DCCA9E` を流用
- ANT+ FE-C メッセージ（13バイト固定長）をそのまま BLE characteristic に読み書きする
- 双方向通信: トレーナーからのテレメトリ受信 + アプリからの負荷制御

## BLE サービス・キャラクタリスティック

| 役割 | UUID | Properties | 説明 |
|------|------|------------|------|
| Service | `6E40FEC1-B5A3-F393-E0A9-E50E24DCCA9E` | - | FE-C Brake Service |
| TX (トレーナー→アプリ) | `6E40FEC2-B5A3-F393-E0A9-E50E24DCCA9E` | Notify | 速度・パワー・ケイデンス等を受信 |
| RX (アプリ→トレーナー) | `6E40FEC3-B5A3-F393-E0A9-E50E24DCCA9E` | Write | 負荷制御コマンドを送信 |

※ TX/RX の命名はトレーナー視点（アプリ視点では TX=Read, RX=Write）

## メッセージフォーマット（13バイト固定）

```
Byte:  [0]    [1]     [2]    [3]      [4]    [5..11]     [12]
Field: SYNC   LENGTH  TYPE   CHANNEL  DP     PAYLOAD     CHECKSUM
Value: 0xA4   0x09    0x4E   0x05     page   (7 bytes)   XOR
```

| バイト | フィールド | 値 | 説明 |
|--------|-----------|-----|------|
| 0 | Sync | `0xA4` | ANT sync byte（固定） |
| 1 | Length | `0x09` | データ長: channel(1) + payload(8) = 9 |
| 2 | Message Type | `0x4E` / `0x4F` | `0x4E` = Broadcast, `0x4F` = Acknowledged |
| 3 | Channel | `0x05` | ANT チャンネル番号（FE-C over BLE では常に 5） |
| 4 | Data Page | varies | FE-C データページ番号 |
| 5-11 | Payload | varies | ページ固有のデータ（7バイト） |
| 12 | Checksum | calculated | バイト 0〜11 の XOR |

### チェックサム計算

```javascript
let checksum = 0;
for (let i = 0; i < 12; i++) checksum ^= msg[i];
msg[12] = checksum;
```

---

## 送信データページ（アプリ→トレーナー: 負荷制御）

### Page 48 (0x30) - Basic Resistance

トレーナーの負荷を 0〜100% で指定する。最もシンプルな制御方法。

```
Byte:  [4]    [5]   [6]   [7]   [8]   [9]   [10]  [11]
       0x30   0xFF  0xFF  0xFF  0xFF  0xFF  0xFF  RESISTANCE
```

| バイト | フィールド | 型 | 解像度 | 範囲 | 説明 |
|--------|-----------|-----|--------|------|------|
| 4 | Data Page | Uint8 | - | 0x30 | ページ番号 |
| 5-10 | Reserved | - | - | 0xFF で埋める | - |
| 11 | Total Resistance | Uint8 | 0.5% | 0〜200 (= 0〜100%) | `percentage / 0.5` |

**例: 50% 負荷** → byte 11 = `50 / 0.5 = 100 (0x64)`

```
A4 09 4E 05 30 FF FF FF FF FF FF 64 [checksum]
```

### Page 49 (0x31) - Target Power（ERG モード）

指定ワット数を維持するよう負荷を自動調整する。ケイデンスに関係なく一定パワー。

```
Byte:  [4]    [5]   [6]   [7]   [8]   [9]   [10]       [11]
       0x31   0xFF  0xFF  0xFF  0xFF  0xFF  POWER_LSB  POWER_MSB
```

| バイト | フィールド | 型 | 解像度 | 範囲 | 説明 |
|--------|-----------|-----|--------|------|------|
| 4 | Data Page | Uint8 | - | 0x31 | ページ番号 |
| 5-9 | Reserved | - | - | 0xFF で埋める | - |
| 10-11 | Target Power | Uint16 LE | 0.25 W | 0〜4000 W | `watts / 0.25` |

**例: 100W** → `100 / 0.25 = 400 = 0x0190` → byte 10 = 0x90, byte 11 = 0x01

```
A4 09 4E 05 31 FF FF FF FF FF 90 01 [checksum]
```

**例: 300W** → `300 / 0.25 = 1200 = 0x04B0` → byte 10 = 0xB0, byte 11 = 0x04

```
A4 09 4E 05 31 FF FF FF FF FF B0 04 [checksum]
```

### Page 50 (0x32) - Wind Resistance

風・空気抵抗をシミュレーションする。

```
Byte:  [4]    [5]   [6]   [7]   [8]   [9]          [10]         [11]
       0x32   0xFF  0xFF  0xFF  0xFF  WIND_COEFF   WIND_SPEED   DRAFTING
```

| バイト | フィールド | 型 | 解像度 | 範囲 | デフォルト | 説明 |
|--------|-----------|-----|--------|------|-----------|------|
| 9 | Wind Resistance Coefficient | Uint8 | 0.01 kg/m | 0〜1.86 | 0.51 | 前面面積×抗力係数×空気密度 |
| 10 | Wind Speed | Int8 | 1 km/h | -127〜+127 | 0 | `value + 127` でエンコード |
| 11 | Drafting Factor | Uint8 | 0.01 | 0〜1.00 | 1.0 | 1.0=ドラフティングなし |

**エンコード:** 風速 0 km/h → byte 10 = `0 + 127 = 127 (0x7F)`

### Page 51 (0x33) - Track Resistance（勾配シミュレーション）

**地形連動に最も適したページ。** Zwift 等のアプリはこのページで登り坂をシミュレーションする。

```
Byte:  [4]    [5]   [6]   [7]   [8]   [9]         [10]        [11]
       0x33   0xFF  0xFF  0xFF  0xFF  GRADE_LSB   GRADE_MSB   CRR
```

| バイト | フィールド | 型 | 解像度 | 範囲 | デフォルト | 説明 |
|--------|-----------|-----|--------|------|-----------|------|
| 4 | Data Page | Uint8 | - | - | - | 0x33 |
| 5-8 | Reserved | - | - | - | 0xFF | - |
| 9-10 | Grade（勾配） | Uint16 LE | 0.01% | -200%〜+200% | 0% | `(grade% + 200) / 0.01` |
| 11 | 転がり抵抗係数 (CRR) | Uint8 | 5×10⁻⁵ | 0〜0.0127 | 0.004 | `CRR / 0.00005` |

**エンコード例:**

| 勾配 | 計算 | byte 9 (LSB) | byte 10 (MSB) |
|------|------|-------------|---------------|
| 0% (平地) | `(0 + 200) / 0.01 = 20000 = 0x4E20` | 0x20 | 0x4E |
| +5% (登り) | `(5 + 200) / 0.01 = 20500 = 0x5014` | 0x14 | 0x50 |
| +10% (急登) | `(10 + 200) / 0.01 = 21000 = 0x5208` | 0x08 | 0x52 |
| -3% (下り) | `(-3 + 200) / 0.01 = 19700 = 0x4CF4` | 0xF4 | 0x4C |

**CRR 例:** アスファルト 0.004 → `0.004 / 0.00005 = 80 (0x50)`

### Page 55 (0x37) - User Configuration

ユーザー体重・自転車重量を送信。勾配シミュレーションの精度に影響する。

| バイト | フィールド | 型 | 解像度 | デフォルト | 説明 |
|--------|-----------|-----|--------|-----------|------|
| 4 | Data Page | Uint8 | - | - | 0x37 |
| 5-6 | User Weight | Uint16 LE | 0.01 kg | 75 kg | ユーザー体重 |
| 7 | Reserved | - | - | 0xFF | - |
| 8 bits 0-3 | Diameter Offset | Uint4 | - | 0xF | ホイール径オフセット |
| 8 bits 4-7 + byte 9 | Bike Weight | Uint12 | 0.05 kg | 8 kg | 自転車重量 |
| 10 | Wheel Diameter | Uint8 | 0.01 m | 0.7 m | ホイール径 |
| 11 | Gear Ratio | Uint8 | 0.03 | 0 | 0=無効 |

---

## 受信データページ（トレーナー→アプリ: テレメトリ）

### Page 16 (0x10) - General FE Data

約250ms間隔で送信される一般テレメトリ。

| バイトオフセット | フィールド | 型 | 解像度 | 説明 |
|----------------|-----------|-----|--------|------|
| 0 (= byte 4) | Data Page | Uint8 | - | 0x10 |
| 1 | Equipment Type | Uint8 | - | 0x19 = trainer |
| 2 | Elapsed Time | Uint8 | 0.25 s | 64秒でロールオーバー |
| 3 | Distance | Uint8 | 1 m | 256mでロールオーバー |
| 4-5 | Speed | Uint16 LE | 0.001 m/s | `× 3.6` で km/h |
| 6 | Heart Rate | Uint8 | 1 bpm | 255 = 無効 |
| 7 bits 4-7 | FE State | Uint4 | - | 機器状態 |

### Page 25 (0x19) - Trainer-Specific Data

パワーとケイデンスを含むトレーナー固有データ。

| バイトオフセット | フィールド | 型 | 解像度 | 説明 |
|----------------|-----------|-----|--------|------|
| 0 (= byte 4) | Data Page | Uint8 | - | 0x19 |
| 1 | Update Event Count | Uint8 | - | イベントごとにインクリメント |
| 2 | Instantaneous Cadence | Uint8 | 1 RPM | 255 = 無効 |
| 3-4 | Accumulated Power | Uint16 LE | 1 W | 累積、65536でロールオーバー |
| 5-6 bits 0-11 | Instantaneous Power | Uint12 | 1 W | 現在のパワー |
| 6 bits 4-7 | Trainer Status | Uint4 | - | ステータスフラグ |
| 7 bits 4-7 | FE State | Uint4 | - | 機器状態 |

### Page 71 (0x47) - Command Status

制御コマンドの応答確認。

| バイトオフセット | フィールド | 説明 |
|----------------|-----------|------|
| 0 (= byte 4) | Data Page | 0x47 |
| 1 | Last Received Command | 最後に受信したコマンドのページ番号 |
| 2 | Sequence Number | コマンドごとにインクリメント |
| 3 | Status | 0=成功, 1=失敗, 2=未対応, 3=拒否, 255=未初期化 |
| 4-7 | Response Data | コマンド固有のレスポンス |

---

## Tacx NEO 固有拡張

### Page 252 (0xFC) - NEO Specific Modes

Tacx NEO シリーズ固有の路面シミュレーション等。

| バイト | フィールド | 説明 |
|--------|-----------|------|
| 4 | Data Page | 0xFC |
| 5 | Sub-page | 0x00 |
| 6 | Isokinetic Mode | 0=オフ, 1=オン |
| 7 | Isokinetic Speed | 速度 (0.05 m/s 単位) |
| 9 | Road Surface Type | 0〜9 (コンクリート、石畳等) |
| 10 | Road Surface Intensity | 0〜100 (255=デフォルト) |

---

## Web Bluetooth 実装例

```javascript
// --- 接続 ---
const device = await navigator.bluetooth.requestDevice({
  filters: [{ services: ['6e40fec1-b5a3-f393-e0a9-e50e24dcca9e'] }]
});
const server = await device.gatt.connect();
const service = await server.getPrimaryService('6e40fec1-b5a3-f393-e0a9-e50e24dcca9e');
const txChar = await service.getCharacteristic('6e40fec2-b5a3-f393-e0a9-e50e24dcca9e');
const rxChar = await service.getCharacteristic('6e40fec3-b5a3-f393-e0a9-e50e24dcca9e');

// --- テレメトリ受信 ---
txChar.addEventListener('characteristicvaluechanged', (event) => {
  const data = new Uint8Array(event.target.value.buffer);
  // data[0]=0xA4, data[4]=DataPage
  if (data[4] === 0x10) {
    // General FE Data
    const speedRaw = data[8] | (data[9] << 8);
    const speedKmh = (speedRaw * 0.001) * 3.6;
  }
  if (data[4] === 0x19) {
    // Trainer Specific
    const cadence = data[6]; // RPM
    const powerRaw = (data[9] | (data[10] << 8)) & 0x0FFF;
    const powerWatts = powerRaw; // 1W resolution
  }
});
await txChar.startNotifications();

// --- メッセージ構築ヘルパー ---
function buildFecMessage(payload) {
  const msg = new Uint8Array(13);
  msg[0] = 0xA4; // sync
  msg[1] = 0x09; // length
  msg[2] = 0x4E; // broadcast data
  msg[3] = 0x05; // channel
  msg.set(payload, 4); // 8-byte payload
  let checksum = 0;
  for (let i = 0; i < 12; i++) checksum ^= msg[i];
  msg[12] = checksum;
  return msg;
}

// --- 勾配シミュレーション (Page 51) ---
function setGrade(gradePercent, crr = 0.004) {
  const payload = new Uint8Array(8);
  payload[0] = 0x33; // page 51
  payload[1] = 0xFF;
  payload[2] = 0xFF;
  payload[3] = 0xFF;
  payload[4] = 0xFF;
  const gradeVal = Math.round((gradePercent + 200) / 0.01);
  payload[5] = gradeVal & 0xFF;        // LSB
  payload[6] = (gradeVal >> 8) & 0xFF;  // MSB
  payload[7] = Math.round(crr / 0.00005);
  return rxChar.writeValue(buildFecMessage(payload));
}

// --- ターゲットパワー (Page 49) ---
function setTargetPower(watts) {
  const payload = new Uint8Array(8);
  payload[0] = 0x31; // page 49
  payload.fill(0xFF, 1, 6);
  const powerVal = Math.round(watts / 0.25);
  payload[6] = powerVal & 0xFF;        // LSB
  payload[7] = (powerVal >> 8) & 0xFF;  // MSB
  return rxChar.writeValue(buildFecMessage(payload));
}

// --- ベーシック負荷 (Page 48) ---
function setBasicResistance(percent) {
  const payload = new Uint8Array(8);
  payload[0] = 0x30; // page 48
  payload.fill(0xFF, 1, 7);
  payload[7] = Math.round(percent / 0.5);
  return rxChar.writeValue(buildFecMessage(payload));
}
```

---

## 対応トレーナーモデル

| モデル | FE-C over BLE | ANT+ FE-C | BLE FTMS |
|--------|:---:|:---:|:---:|
| Tacx NEO (初代) | o | o | x |
| Tacx NEO 2T Smart | o | o | o |
| Tacx NEO Bike Smart | FW依存 | o | FW依存 |
| Tacx Vortex Smart | x (独自) | o | x |
| 新型 (NEO 3M等) | x | o | o |

※ Think X2111 は FE-C over BLE + CPS (0x1818) を搭載

---

## オープンソース実装・リファレンス

### 公式仕様書

- **"How-to FE-C over BLE v1_0_0.pdf"** (Tacx/Kinomap)
  - https://github.com/abellono/tacx-ios-bluetooth-example (リポジトリ内に PDF)
  - https://github.com/jedla22/BleTrainerControl (同 PDF)

### JavaScript / TypeScript (Web Bluetooth)

| プロジェクト | 説明 |
|-------------|------|
| [Auuki](https://github.com/dvmarinoff/Auuki) | Web版サイクリングアプリ。`src/ble/fec/` に完全な FE-C 実装 |
| [bfree](https://github.com/bfree-trainer/bfree) | Next.js + TypeScript。`lib/ble/trainer.ts` に FE-C 実装 |

### Python

| プロジェクト | 説明 |
|-------------|------|
| [pycycling](https://github.com/zacharyedwardbull/pycycling) | `tacx_trainer_control` モジュール。API が整理されている |

### iOS (Objective-C)

| プロジェクト | 説明 |
|-------------|------|
| [tacx-ios-bluetooth-example](https://github.com/abellono/tacx-ios-bluetooth-example) | Tacx/Kinomap 公式リファレンス実装 |
| [BleTrainerControl](https://github.com/jedla22/BleTrainerControl) | 上記のフォーク |

### C++ / Arduino / ESP32

| プロジェクト | 説明 |
|-------------|------|
| [simcline](https://github.com/Berg0162/simcline) | ESP32 で FE-C をインターセプトし物理傾斜台を制御 |
| [ftms_emu](https://github.com/OevreFlataeker/ftms_emu) | ESP32 で FTMS/CPS/FE-C をエミュレート |

### その他

| プロジェクト | 言語 | 説明 |
|-------------|------|------|
| [GoldenCheetah](https://github.com/GoldenCheetah/GoldenCheetah) | C++ | `src/ANT/ANT.h` に FE-C 定数定義 |
| [TrainerControl](https://github.com/alex-hhh/TrainerControl) | Racket | ANT+ FE-C テレメトリ・制御サーバ |

### 参考記事

- [DC Rainmaker - Everything You Wanted to Know About Trainers](https://www.dcrainmaker.com/2016/07/everything-wanted-trainers.html)
- [Garmin Developer - Tacx Trainer Communication](https://developer.garmin.com/tacx-trainer/overview/)
- [Blog: Making a Cycling Game - Bluetooth](https://blog.lazerwalker.com/2019/02/15/bike-game-part-2.html)
