# BLE CSC (Cycling Speed and Cadence) プロファイル仕様

Bluetooth SIG 標準規格。ホイール回転数とクランク回転数の累積値・タイムスタンプから速度・ケイデンスを算出する。

## 概要

- Service UUID: `0x1816` (Cycling Speed and Cadence)
- 速度・ケイデンスは「計算済みの値」ではなく、累積回転数とタイムスタンプの差分から算出する
- デバイスによってホイールデータのみ、クランクデータのみ、または両方を持つ
- 速度算出にはホイール周長の設定が必要

## BLE サービス・キャラクタリスティック

| 役割 | UUID | Properties | 説明 |
|------|------|------------|------|
| Service | `0x1816` | - | Cycling Speed and Cadence |
| CSC Measurement | `0x2A5B` | Notify | 回転数・タイムスタンプ（メインデータ） |
| CSC Feature | `0x2A5C` | Read | デバイスがサポートする機能フラグ |
| Sensor Location | `0x2A5D` | Read | センサー取付位置 |
| SC Control Point | `0x2A55` | Write, Indicate | 累積値リセット等の制御 |

---

## CSC Feature (0x2A5C)

デバイスがどのデータを提供するかを示す。接続時に一度読み取ればよい。

| ビット | フィールド | 説明 |
|--------|-----------|------|
| 0 | Wheel Revolution Data Supported | ホイール回転データ対応 |
| 1 | Crank Revolution Data Supported | クランク回転データ対応 |
| 2 | Multiple Sensor Locations Supported | 複数取付位置対応 |

**例:** Feature = `0x03` → ホイール・クランク両対応

---

## CSC Measurement (0x2A5B) — メインデータ

### Flags フィールド

| 型 | サイズ | 説明 |
|----|--------|------|
| Uint8 | 1 バイト | 後続データの有無を示す |

| ビット | フィールド | 説明 |
|--------|-----------|------|
| 0 | Wheel Revolution Data Present | 1 = ホイールデータあり |
| 1 | Crank Revolution Data Present | 1 = クランクデータあり |

### バイトレイアウト

Flags の値によって後続フィールドの有無・オフセットが変わる。

#### パターン A: ホイールのみ (Flags = 0x01)

```
Byte:  [0]     [1..4]              [5..6]
Field: FLAGS   WHEEL_REVOLUTIONS   WHEEL_EVENT_TIME
```

#### パターン B: クランクのみ (Flags = 0x02)

```
Byte:  [0]     [1..2]              [3..4]
Field: FLAGS   CRANK_REVOLUTIONS   CRANK_EVENT_TIME
```

#### パターン C: ホイール＋クランク (Flags = 0x03)

```
Byte:  [0]     [1..4]              [5..6]              [7..8]              [9..10]
Field: FLAGS   WHEEL_REVOLUTIONS   WHEEL_EVENT_TIME    CRANK_REVOLUTIONS   CRANK_EVENT_TIME
```

### フィールド詳細

| フィールド | 型 | サイズ | 解像度 | ロールオーバー | 説明 |
|-----------|-----|--------|--------|--------------|------|
| Cumulative Wheel Revolutions | Uint32 LE | 4 bytes | 1 回転 | 4,294,967,296 | ホイール累積回転数 |
| Last Wheel Event Time | Uint16 LE | 2 bytes | 1/1024 秒 | 65,536 (≈64秒) | 最終ホイールイベント時刻 |
| Cumulative Crank Revolutions | Uint16 LE | 2 bytes | 1 回転 | 65,536 | クランク累積回転数 |
| Last Crank Event Time | Uint16 LE | 2 bytes | 1/1024 秒 | 65,536 (≈64秒) | 最終クランクイベント時刻 |

---

## 速度の算出

### 前提

- 2回以上の通知が必要（初回は前回値がないため計算不可）
- ホイール周長（mm）の設定が必要（700×25c = 2105mm が一般的）

### 計算式

```
deltaRevs = currentWheelRevs - previousWheelRevs
deltaTime = currentWheelTime - previousWheelTime

speed (m/s) = deltaRevs × wheelCircumference(m) / (deltaTime / 1024)
speed (km/h) = speed (m/s) × 3.6
```

### ロールオーバー処理

タイムスタンプとカウンターはそれぞれ固定ビット幅で循環する。差分が負になった場合は最大値を加算する。

```javascript
let deltaRevs = wheelRevs - prevWheelRevs;
if (deltaRevs < 0) deltaRevs += 4294967296;  // 32-bit rollover

let deltaTime = wheelTime - prevWheelTime;
if (deltaTime < 0) deltaTime += 65536;       // 16-bit rollover
```

### 代表的なホイール周長

| タイヤサイズ | 周長 (mm) |
|------------|-----------|
| 700×23c | 2096 |
| 700×25c | 2105 |
| 700×28c | 2136 |
| 700×32c | 2155 |
| 650×25c (650B) | 1953 |
| 26×2.0 (MTB) | 2055 |
| 29×2.1 (MTB) | 2288 |

---

## ケイデンスの算出

### 計算式

```
deltaRevs = currentCrankRevs - previousCrankRevs
deltaTime = currentCrankTime - previousCrankTime

cadence (rpm) = (deltaRevs / (deltaTime / 1024)) × 60
```

### ロールオーバー処理

```javascript
let deltaRevs = crankRevs - prevCrankRevs;
if (deltaRevs < 0) deltaRevs += 65536;       // 16-bit rollover

let deltaTime = crankTime - prevCrankTime;
if (deltaTime < 0) deltaTime += 65536;       // 16-bit rollover
```

---

## 停止検出

CSC は「変化があった時のみ」通知を送るデバイスが多く、停止中は通知が来ない場合がある。一般的に **3秒間** データ更新がなければ停止と判断する。

```javascript
const STOP_TIMEOUT_MS = 3000;
let lastUpdateTime = Date.now();

// 通知受信時に更新
lastUpdateTime = Date.now();

// タイマーで停止検出
setInterval(() => {
  if (Date.now() - lastUpdateTime > STOP_TIMEOUT_MS) {
    speed = 0;
    cadence = 0;
  }
}, 1000);
```

---

## SC Control Point (0x2A55)

累積回転数のリセット等に使用する。Write + Indicate で応答を受け取る。

| OpCode | パラメータ | 説明 |
|--------|-----------|------|
| 0x01 | Uint32 LE (累積値) | 累積ホイール回転数をセット |
| 0x02 | なし | センサー取付位置を更新（Multiple Locations 対応時） |
| 0x03 | なし | サポートセンサー位置リストを要求 |

### レスポンス (Indicate)

```
Byte:  [0]        [1]              [2]         [3...]
Field: RESPONSE   REQUEST_OPCODE   RESULT      RESPONSE_PARAMETER
Value: 0x10       (元の OpCode)    (結果)
```

| Result | 説明 |
|--------|------|
| 0x01 | 成功 |
| 0x02 | OpCode 未対応 |
| 0x03 | パラメータ不正 |
| 0x04 | 処理失敗 |

---

## Sensor Location (0x2A5D)

| 値 | 位置 |
|----|------|
| 0 | Other |
| 1 | Top of shoe |
| 2 | In shoe |
| 3 | Hip |
| 4 | Front Wheel |
| 5 | Left Crank |
| 6 | Right Crank |
| 7 | Left Pedal |
| 8 | Right Pedal |
| 9 | Front Hub |
| 10 | Rear Dropout |
| 11 | Chainstay |
| 12 | Rear Wheel |
| 13 | Rear Hub |
| 14 | Chest |
| 15 | Spider |
| 16 | Chain Ring |

---

## Web Bluetooth 実装例

```javascript
// --- 接続 ---
const device = await navigator.bluetooth.requestDevice({
  filters: [{ services: ['cycling_speed_and_cadence'] }]
  // 数値でも可: filters: [{ services: [0x1816] }]
});
const server = await device.gatt.connect();
const service = await server.getPrimaryService('cycling_speed_and_cadence');
const cscMeasurement = await service.getCharacteristic('csc_measurement');

// --- 状態管理 ---
const WHEEL_CIRCUMFERENCE_MM = 2105;
let prevWheelRevs = null, prevWheelTime = null;
let prevCrankRevs = null, prevCrankTime = null;

// --- 通知受信 ---
cscMeasurement.addEventListener('characteristicvaluechanged', (event) => {
  const dv = event.target.value;
  const flags = dv.getUint8(0);
  const hasWheelData = !!(flags & 0x01);
  const hasCrankData = !!(flags & 0x02);
  let offset = 1;

  // ホイールデータ → 速度
  if (hasWheelData) {
    const wheelRevs = dv.getUint32(offset, true);
    const wheelTime = dv.getUint16(offset + 4, true);
    offset += 6;

    if (prevWheelRevs !== null) {
      let deltaRevs = wheelRevs - prevWheelRevs;
      let deltaTime = wheelTime - prevWheelTime;
      if (deltaRevs < 0) deltaRevs += 4294967296;
      if (deltaTime < 0) deltaTime += 65536;

      if (deltaTime > 0 && deltaRevs > 0) {
        const wheelCircM = WHEEL_CIRCUMFERENCE_MM / 1000;
        const timeSec = deltaTime / 1024;
        const speed = (deltaRevs * wheelCircM / timeSec) * 3.6; // km/h
        console.log(`Speed: ${speed.toFixed(1)} km/h`);
      }
    }
    prevWheelRevs = wheelRevs;
    prevWheelTime = wheelTime;
  }

  // クランクデータ → ケイデンス
  if (hasCrankData) {
    const crankRevs = dv.getUint16(offset, true);
    const crankTime = dv.getUint16(offset + 2, true);
    offset += 4;

    if (prevCrankRevs !== null) {
      let deltaRevs = crankRevs - prevCrankRevs;
      let deltaTime = crankTime - prevCrankTime;
      if (deltaRevs < 0) deltaRevs += 65536;
      if (deltaTime < 0) deltaTime += 65536;

      if (deltaTime > 0 && deltaRevs > 0) {
        const timeSec = deltaTime / 1024;
        const cadence = (deltaRevs / timeSec) * 60; // rpm
        console.log(`Cadence: ${cadence.toFixed(0)} rpm`);
      }
    }
    prevCrankRevs = crankRevs;
    prevCrankTime = crankTime;
  }
});

await cscMeasurement.startNotifications();
```

### Feature 読み取り

```javascript
const cscFeature = await service.getCharacteristic('csc_feature');
const featureValue = await cscFeature.readValue();
const features = featureValue.getUint16(0, true);
const hasWheel = !!(features & 0x01);
const hasCrank = !!(features & 0x02);
console.log(`Wheel: ${hasWheel}, Crank: ${hasCrank}`);
```

### 累積回転数リセット

```javascript
const controlPoint = await service.getCharacteristic('sc_control_point');
await controlPoint.startNotifications();
controlPoint.addEventListener('characteristicvaluechanged', (event) => {
  const dv = event.target.value;
  const response = dv.getUint8(0);   // 0x10 = Response
  const opCode = dv.getUint8(1);     // 要求した OpCode
  const result = dv.getUint8(2);     // 0x01 = 成功
  console.log(`Control Point response: opCode=${opCode}, result=${result}`);
});

// 累積ホイール回転数を 0 にリセット
const resetCmd = new Uint8Array([0x01, 0x00, 0x00, 0x00, 0x00]);
await controlPoint.writeValue(resetCmd);
```

---

## デバイス例

| デバイス | ホイール | クランク | 備考 |
|---------|:------:|:------:|------|
| Garmin Speed Sensor 2 | o | x | ANT+ / BLE 両対応 |
| Garmin Cadence Sensor 2 | x | o | ANT+ / BLE 両対応 |
| Wahoo RPM Speed | o | x | BLE のみ |
| Wahoo RPM Cadence | x | o | BLE のみ |
| Wahoo KICKR (トレーナー) | o | o | FTMS/CPS も同時公開 |
| Magene S3+ | o | o | デュアルモード（速度+ケイデンス）|
| CooSpo BK467 | o | o | 低価格デュアル |

※ スマートトレーナーの多くは CSC (0x1816) ではなく CPS (0x1818) や FTMS (0x1826) でホイール・クランクデータを提供する

---

## CPS (0x1818) との違い

CSC と CPS はホイール・クランクのデータ形式がほぼ同一だが、いくつか重要な差異がある。

| 項目 | CSC (0x1816) | CPS (0x1818) |
|------|-------------|-------------|
| パワーデータ | なし | あり（常に含まれる） |
| Flags サイズ | Uint8 (1 byte) | Uint16 (2 bytes) |
| ホイールタイムスタンプ解像度 | 1/1024 秒 | **1/2048 秒** |
| クランクタイムスタンプ解像度 | 1/1024 秒 | 1/1024 秒 |
| Flags ビット位置（ホイール） | bit 0 | bit 4 |
| Flags ビット位置（クランク） | bit 1 | bit 5 |

**注意:** CPS のホイールタイムスタンプは **1/2048 秒** 解像度で、CSC の 1/1024 秒と異なる。速度計算の除数を間違えると2倍の誤差が出る。

---

## 公式仕様

- **Bluetooth SIG — GATT Specification Supplement**
  - CSC Measurement: https://www.bluetooth.com/specifications/specs/gatt-specification-supplement/
  - Assigned Numbers (Service UUIDs): https://www.bluetooth.com/specifications/assigned-numbers/
- **Bluetooth SIG — Cycling Speed and Cadence Service (CSCS) 1.0**
  - https://www.bluetooth.com/specifications/specs/cycling-speed-and-cadence-service-1-0/

## オープンソース実装・リファレンス

### JavaScript / TypeScript (Web Bluetooth)

| プロジェクト | 説明 |
|-------------|------|
| [AntiboticsRT](https://github.com/niccolorossi/AntiboticsRT) | Web Bluetooth ベースのリアルタイムセンサーアプリ。CSC パーシング実装あり |
| [Auuki](https://github.com/dvmarinoff/Auuki) | Web版サイクリングアプリ。`src/ble/csc/` に CSC 実装 |
| [bfree](https://github.com/bfree-trainer/bfree) | Next.js + TypeScript。BLE CSC/CPS/FTMS 対応 |

### Python

| プロジェクト | 説明 |
|-------------|------|
| [pycycling](https://github.com/zacharyedwardbull/pycycling) | `cycling_speed_cadence_service` モジュール。Bleak ベース |

### C++ / Arduino / ESP32

| プロジェクト | 説明 |
|-------------|------|
| [ESP32_BLE_Cycling](https://github.com/rlorigro/ESP32_BLE_Cycling) | ESP32 で CSC をエミュレート |
| [CyclingSpeedCadence](https://github.com/Georg-Auer/CyclingSpeedCadence) | Arduino BLE CSC 実装 |
