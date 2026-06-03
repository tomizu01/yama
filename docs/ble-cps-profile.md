# BLE CPS (Cycling Power Service) プロファイル仕様

Bluetooth SIG 標準規格。瞬時パワー（ワット）を中心に、オプションでホイール回転数・クランク回転数・トルク・ペダルバランス等を提供する。パワーメーター、スマートトレーナーが実装する。

## 概要

- Service UUID: `0x1818` (Cycling Power)
- 瞬時パワー（Instantaneous Power）は **常に** 含まれる
- ホイール・クランク回転データはオプション（CSC 0x1816 と類似形式だがタイムスタンプ解像度が異なる）
- Flags が Uint16 と大きく、多数のオプションフィールドを持つ

## BLE サービス・キャラクタリスティック

| 役割 | UUID | Properties | 説明 |
|------|------|------------|------|
| Service | `0x1818` | - | Cycling Power |
| Cycling Power Measurement | `0x2A63` | Notify | パワー・回転数等（メインデータ） |
| Cycling Power Feature | `0x2A65` | Read | デバイスがサポートする機能フラグ |
| Sensor Location | `0x2A5D` | Read | センサー取付位置（CSC と共通） |
| Cycling Power Control Point | `0x2A66` | Write, Indicate | キャリブレーション等の制御 |
| Cycling Power Vector | `0x2A64` | Notify | クランク角度ごとの力・トルク分布（高機能モデルのみ） |

---

## Cycling Power Feature (0x2A65)

デバイスがどのデータ・機能を提供するかを示す。接続時に一度読み取ればよい。

| ビット | フィールド | 説明 |
|--------|-----------|------|
| 0 | Pedal Power Balance Supported | ペダルパワーバランス |
| 1 | Accumulated Torque Supported | 累積トルク |
| 2 | Wheel Revolution Data Supported | ホイール回転データ |
| 3 | Crank Revolution Data Supported | クランク回転データ |
| 4 | Extreme Magnitudes Supported | 極値（力） |
| 5 | Extreme Angles Supported | 極値（角度） |
| 6 | Top/Bottom Dead Spot Angle Supported | 上/下死点角度 |
| 7 | Accumulated Energy Supported | 累積エネルギー |
| 8 | Offset Compensation Indicator Supported | オフセット補正 |
| 9 | Offset Compensation Supported | オフセット補正制御 |
| 10 | Cycling Power Measurement Content Masking | 通知内容マスク |
| 11 | Multiple Sensor Locations Supported | 複数取付位置 |
| 12 | Crank Length Adjustment Supported | クランク長調整 |
| 13 | Chain Length Adjustment Supported | チェーン長調整 |
| 14 | Chain Weight Adjustment Supported | チェーン重量調整 |
| 15 | Span Length Adjustment Supported | スパン長調整 |
| 16 | Sensor Measurement Context | 0=Force, 1=Torque |
| 17 | Instantaneous Measurement Direction | 測定方向 |
| 18 | Factory Calibration Date Supported | 工場キャリブレーション日 |
| 19 | Enhanced Offset Compensation Supported | 拡張オフセット補正 |
| 20-21 | Distribute System Support | 0=未指定, 1=非分散, 2=分散, 3=RFU |

---

## Cycling Power Measurement (0x2A63) — メインデータ

### Flags フィールド

| 型 | サイズ | 説明 |
|----|--------|------|
| Uint16 LE | 2 バイト | 後続オプションデータの有無を示す |

| ビット | フィールド | 説明 |
|--------|-----------|------|
| 0 | Pedal Power Balance Present | 1 = ペダルバランスあり |
| 1 | Pedal Power Balance Reference | 0 = Unknown, 1 = Left |
| 2 | Accumulated Torque Present | 1 = 累積トルクあり |
| 3 | Accumulated Torque Source | 0 = Wheel, 1 = Crank |
| 4 | Wheel Revolution Data Present | 1 = ホイール回転データあり |
| 5 | Crank Revolution Data Present | 1 = クランク回転データあり |
| 6 | Extreme Force Magnitudes Present | 1 = 極値力あり |
| 7 | Extreme Torque Magnitudes Present | 1 = 極値トルクあり |
| 8 | Extreme Angles Present | 1 = 極値角度あり |
| 9 | Top Dead Spot Angle Present | 1 = 上死点角度あり |
| 10 | Bottom Dead Spot Angle Present | 1 = 下死点角度あり |
| 11 | Accumulated Energy Present | 1 = 累積エネルギーあり |
| 12 | Offset Compensation Indicator | 0 = 未補正, 1 = 補正済み |
| 13-15 | Reserved | - |

### バイトレイアウト

Flags + Instantaneous Power は常に存在し、その後にフラグに応じたオプションフィールドが可変長で続く。

#### 固定部分（常に存在）

```
Byte:  [0..1]   [2..3]
Field: FLAGS    INSTANTANEOUS_POWER
```

#### 全フィールド展開時の並び順

```
Byte:  [0..1]  [2..3]   [4]              [5..6]            [7..10]             [11..12]
Field: FLAGS   POWER    PEDAL_BALANCE    ACC_TORQUE        WHEEL_REVOLUTIONS   WHEEL_EVENT_TIME

       [13..14]            [15..16]           [17..18]             [19..20]
       CRANK_REVOLUTIONS   CRANK_EVENT_TIME   MAX_FORCE_MAGNITUDE  MIN_FORCE_MAGNITUDE

       [21..22]              [23..24]              [25..26]           [27..28]
       MAX_TORQUE_MAGNITUDE  MIN_TORQUE_MAGNITUDE  EXTREME_ANGLES     TOP_DEAD_SPOT_ANGLE

       [29..30]               [31..32]
       BOTTOM_DEAD_SPOT_ANGLE ACCUMULATED_ENERGY
```

※ 実際のオフセットはフラグに応じて詰められる（存在しないフィールドの分は詰まる）

### フィールド詳細

| フィールド | 型 | サイズ | 解像度 | 範囲 | 条件 |
|-----------|-----|--------|--------|------|------|
| Instantaneous Power | Sint16 LE | 2 bytes | 1 W | -32768〜32767 | 常に存在 |
| Pedal Power Balance | Uint8 | 1 byte | 0.5% | 0〜100% | Flags bit 0 |
| Accumulated Torque | Uint16 LE | 2 bytes | 1/32 Nm | ロールオーバー 65536 | Flags bit 2 |
| Cumulative Wheel Revolutions | Uint32 LE | 4 bytes | 1 回転 | ロールオーバー 4,294,967,296 | Flags bit 4 |
| Last Wheel Event Time | Uint16 LE | 2 bytes | **1/2048 秒** | ロールオーバー 65,536 (≈32秒) | Flags bit 4 |
| Cumulative Crank Revolutions | Uint16 LE | 2 bytes | 1 回転 | ロールオーバー 65,536 | Flags bit 5 |
| Last Crank Event Time | Uint16 LE | 2 bytes | 1/1024 秒 | ロールオーバー 65,536 (≈64秒) | Flags bit 5 |
| Maximum Force Magnitude | Sint16 LE | 2 bytes | 1 N | - | Flags bit 6 |
| Minimum Force Magnitude | Sint16 LE | 2 bytes | 1 N | - | Flags bit 6 |
| Maximum Torque Magnitude | Sint16 LE | 2 bytes | 1/32 Nm | - | Flags bit 7 |
| Minimum Torque Magnitude | Sint16 LE | 2 bytes | 1/32 Nm | - | Flags bit 7 |
| Extreme Angles | Uint24 | 3 bytes | (下記参照) | - | Flags bit 8 |
| Top Dead Spot Angle | Uint16 LE | 2 bytes | 1 度 | 0〜359 | Flags bit 9 |
| Bottom Dead Spot Angle | Uint16 LE | 2 bytes | 1 度 | 0〜359 | Flags bit 10 |
| Accumulated Energy | Uint16 LE | 2 bytes | 1 kJ | ロールオーバー 65,536 | Flags bit 11 |

### Extreme Angles のエンコード (3 bytes)

```
Byte 0 [bits 0-7] + Byte 1 [bits 0-3] → Maximum Angle (12 bits, 1度単位)
Byte 1 [bits 4-7] + Byte 2 [bits 0-7] → Minimum Angle (12 bits, 1度単位)
```

---

## パワーの取得

パワーは Flags に関係なく常に存在する。

```javascript
const flags = dv.getUint16(0, true);
const power = dv.getInt16(2, true); // Sint16, ワット (W)
```

**注意:** `getInt16`（符号付き）を使うこと。一部のデバイスは回生ブレーキ等で負のパワー値を返すことがある。

---

## 速度の算出（ホイール回転データ）

### CSC との重要な違い: タイムスタンプ解像度

| プロファイル | ホイールタイムスタンプ解像度 |
|-------------|--------------------------|
| CSC (0x1816) | 1/1024 秒 |
| **CPS (0x1818)** | **1/2048 秒** |

**これを間違えると速度が2倍ズレる。**

### 計算式

```
deltaRevs = currentWheelRevs - previousWheelRevs
deltaTime = currentWheelTime - previousWheelTime

speed (m/s) = deltaRevs × wheelCircumference(m) / (deltaTime / 2048)
speed (km/h) = speed (m/s) × 3.6
```

### ロールオーバー処理

```javascript
let deltaRevs = wheelRevs - prevWheelRevs;
if (deltaRevs < 0) deltaRevs += 4294967296;  // 32-bit rollover

let deltaTime = wheelTime - prevWheelTime;
if (deltaTime < 0) deltaTime += 65536;       // 16-bit rollover
```

---

## ケイデンスの算出（クランク回転データ）

CSC と同じ 1/1024 秒解像度。計算式も同一。

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

## 可変長パーシングの実装

CPS Measurement はオプションフィールドが多いため、Flags に基づいてオフセットを進めながらパースする必要がある。

```javascript
function parseCpsMeasurement(dv) {
  const flags = dv.getUint16(0, true);
  let offset = 2;

  // パワー（常に存在）
  const power = dv.getInt16(offset, true);
  offset += 2;

  // Pedal Power Balance (Flags bit 0)
  let pedalBalance = null;
  if (flags & 0x0001) {
    pedalBalance = dv.getUint8(offset) * 0.5; // %
    offset += 1;
  }

  // Accumulated Torque (Flags bit 2)
  let accTorque = null;
  if (flags & 0x0004) {
    accTorque = dv.getUint16(offset, true) / 32; // Nm
    offset += 2;
  }

  // Wheel Revolution Data (Flags bit 4)
  let wheelRevs = null, wheelTime = null;
  if (flags & 0x0010) {
    wheelRevs = dv.getUint32(offset, true);
    wheelTime = dv.getUint16(offset + 4, true); // 1/2048 秒
    offset += 6;
  }

  // Crank Revolution Data (Flags bit 5)
  let crankRevs = null, crankTime = null;
  if (flags & 0x0020) {
    crankRevs = dv.getUint16(offset, true);
    crankTime = dv.getUint16(offset + 2, true); // 1/1024 秒
    offset += 4;
  }

  // Extreme Force Magnitudes (Flags bit 6)
  let maxForce = null, minForce = null;
  if (flags & 0x0040) {
    maxForce = dv.getInt16(offset, true);     // N
    minForce = dv.getInt16(offset + 2, true); // N
    offset += 4;
  }

  // Extreme Torque Magnitudes (Flags bit 7)
  let maxTorque = null, minTorque = null;
  if (flags & 0x0080) {
    maxTorque = dv.getInt16(offset, true) / 32;     // Nm
    minTorque = dv.getInt16(offset + 2, true) / 32; // Nm
    offset += 4;
  }

  // Extreme Angles (Flags bit 8)
  let maxAngle = null, minAngle = null;
  if (flags & 0x0100) {
    const b0 = dv.getUint8(offset);
    const b1 = dv.getUint8(offset + 1);
    const b2 = dv.getUint8(offset + 2);
    maxAngle = (b0 | ((b1 & 0x0F) << 8));         // 度
    minAngle = ((b1 >> 4) | (b2 << 4));            // 度
    offset += 3;
  }

  // Top Dead Spot Angle (Flags bit 9)
  let topDeadSpot = null;
  if (flags & 0x0200) {
    topDeadSpot = dv.getUint16(offset, true); // 度
    offset += 2;
  }

  // Bottom Dead Spot Angle (Flags bit 10)
  let bottomDeadSpot = null;
  if (flags & 0x0400) {
    bottomDeadSpot = dv.getUint16(offset, true); // 度
    offset += 2;
  }

  // Accumulated Energy (Flags bit 11)
  let accEnergy = null;
  if (flags & 0x0800) {
    accEnergy = dv.getUint16(offset, true); // kJ
    offset += 2;
  }

  return {
    power, pedalBalance, accTorque,
    wheelRevs, wheelTime, crankRevs, crankTime,
    maxForce, minForce, maxTorque, minTorque,
    maxAngle, minAngle, topDeadSpot, bottomDeadSpot,
    accEnergy
  };
}
```

---

## Cycling Power Control Point (0x2A66)

キャリブレーション・クランク長設定等に使用する。Write + Indicate。

### OpCode 一覧

| OpCode | パラメータ | 説明 |
|--------|-----------|------|
| 0x01 | なし | オフセット補正手続きをセット |
| 0x02 | Uint8 (Content Mask) | 通知内容マスクを更新 |
| 0x03 | なし | サポートセンサー位置リストを要求 |
| 0x04 | Uint16 LE (0.5mm 単位) | クランク長を設定 |
| 0x05 | なし | クランク長を要求 |
| 0x06 | Uint16 LE (0.5mm 単位) | チェーン長を設定 |
| 0x07 | なし | チェーン長を要求 |
| 0x08 | Uint16 LE (0.01kg 単位) | チェーン重量を設定 |
| 0x09 | なし | チェーン重量を要求 |
| 0x0A | Uint16 LE (0.5mm 単位) | スパン長を設定 |
| 0x0B | なし | スパン長を要求 |
| 0x0C | なし | 工場キャリブレーション日を要求 |
| 0x0D | Uint32 LE | 拡張オフセット補正 |
| 0x0E | Sint16 LE (0.25W 単位) | サンプリングレートを設定 |
| 0x0F | なし | 工場キャリブレーション日を要求 |
| 0x20 | Response | レスポンスコード |

### レスポンス (Indicate)

```
Byte:  [0]        [1]              [2]         [3...]
Field: RESPONSE   REQUEST_OPCODE   RESULT      RESPONSE_PARAMETER
Value: 0x20       (元の OpCode)    (結果)
```

| Result | 説明 |
|--------|------|
| 0x01 | 成功 |
| 0x02 | OpCode 未対応 |
| 0x03 | パラメータ不正 |
| 0x04 | 処理失敗 |

---

## Cycling Power Vector (0x2A64)

高機能パワーメーターが提供するクランク角度ごとの力・トルク分布。通常のアプリケーションでは使用しないことが多い。

### Flags

| ビット | フィールド | 説明 |
|--------|-----------|------|
| 0 | Crank Revolution Data Present | クランク回転データあり |
| 1 | First Crank Measurement Angle Present | 最初のクランク測定角度あり |
| 2 | Instantaneous Force Magnitude Array Present | 瞬時力配列あり |
| 3 | Instantaneous Torque Magnitude Array Present | 瞬時トルク配列あり |
| 4-5 | Instantaneous Measurement Direction | 00=Unknown, 01=Tangential, 10=Radial, 11=Lateral |

---

## Web Bluetooth 実装例

```javascript
// --- 接続 ---
// optionalServices で追加サービス（FE-C 等）も指定可能
const device = await navigator.bluetooth.requestDevice({
  filters: [{ services: [0x1818] }],
  optionalServices: ['6e40fec1-b5a3-f393-e0a9-e50e24dcca9e'] // Tacx FE-C（必要時）
});
const server = await device.gatt.connect();
const service = await server.getPrimaryService(0x1818);
const cpsMeasurement = await service.getCharacteristic(0x2A63);

// --- 状態管理 ---
const WHEEL_CIRCUMFERENCE_MM = 2105;
let prevWheelRevs = null, prevWheelTime = null;
let prevCrankRevs = null, prevCrankTime = null;

// --- 通知受信 ---
cpsMeasurement.addEventListener('characteristicvaluechanged', (event) => {
  const dv = event.target.value;
  const flags = dv.getUint16(0, true);
  let offset = 2;

  // パワー（常に存在）
  const power = dv.getInt16(offset, true);
  offset += 2;
  console.log(`Power: ${power} W`);

  // Pedal Power Balance (bit 0)
  if (flags & 0x0001) offset += 1;

  // Accumulated Torque (bit 2)
  if (flags & 0x0004) offset += 2;

  // ホイールデータ → 速度 (bit 4)
  if (flags & 0x0010) {
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
        const timeSec = deltaTime / 2048; // CPS は 1/2048 秒！
        const speed = (deltaRevs * wheelCircM / timeSec) * 3.6;
        console.log(`Speed: ${speed.toFixed(1)} km/h`);
      }
    }
    prevWheelRevs = wheelRevs;
    prevWheelTime = wheelTime;
  }

  // クランクデータ → ケイデンス (bit 5)
  if (flags & 0x0020) {
    const crankRevs = dv.getUint16(offset, true);
    const crankTime = dv.getUint16(offset + 2, true);
    offset += 4;

    if (prevCrankRevs !== null) {
      let deltaRevs = crankRevs - prevCrankRevs;
      let deltaTime = crankTime - prevCrankTime;
      if (deltaRevs < 0) deltaRevs += 65536;
      if (deltaTime < 0) deltaTime += 65536;

      if (deltaTime > 0 && deltaRevs > 0) {
        const timeSec = deltaTime / 1024; // クランクは 1/1024 秒
        const cadence = (deltaRevs / timeSec) * 60;
        console.log(`Cadence: ${cadence.toFixed(0)} rpm`);
      }
    }
    prevCrankRevs = crankRevs;
    prevCrankTime = crankTime;
  }

  // Extreme Force Magnitudes (bit 6)
  if (flags & 0x0040) offset += 4;

  // Extreme Torque Magnitudes (bit 7)
  if (flags & 0x0080) offset += 4;

  // Extreme Angles (bit 8)
  if (flags & 0x0100) offset += 3;

  // Top Dead Spot Angle (bit 9)
  if (flags & 0x0200) offset += 2;

  // Bottom Dead Spot Angle (bit 10)
  if (flags & 0x0400) offset += 2;

  // Accumulated Energy (bit 11)
  if (flags & 0x0800) {
    const energy = dv.getUint16(offset, true);
    offset += 2;
    console.log(`Energy: ${energy} kJ`);
  }
});

await cpsMeasurement.startNotifications();
```

### Feature 読み取り

```javascript
const cpsFeature = await service.getCharacteristic(0x2A65);
const featureValue = await cpsFeature.readValue();
const features = featureValue.getUint32(0, true);
console.log(`Pedal Balance: ${!!(features & 0x01)}`);
console.log(`Acc Torque:    ${!!(features & 0x02)}`);
console.log(`Wheel Data:    ${!!(features & 0x04)}`);
console.log(`Crank Data:    ${!!(features & 0x08)}`);
console.log(`Extreme Force: ${!!(features & 0x10)}`);
console.log(`Extreme Angle: ${!!(features & 0x20)}`);
console.log(`Dead Spot:     ${!!(features & 0x40)}`);
console.log(`Acc Energy:    ${!!(features & 0x80)}`);
```

---

## 典型的なデバイスの Flags パターン

CPS は多数のオプションフィールドを持つが、実際のデバイスが送信する Flags は限られている。

| デバイス種別 | 典型的な Flags | 含まれるデータ |
|-------------|---------------|--------------|
| 片側パワーメーター | `0x0020` | Power + Crank |
| 両側パワーメーター | `0x0021` | Power + Pedal Balance + Crank |
| スマートトレーナー (CPS) | `0x0030` | Power + Wheel + Crank |
| パワーのみ | `0x0000` | Power only |

---

## デバイス例

| デバイス | Power | Wheel | Crank | Pedal Balance | 備考 |
|---------|:-----:|:-----:|:-----:|:------------:|------|
| Stages (片側) | o | x | o | x | 左クランク型 |
| 4iiii Precision | o | x | o | x | 左クランク型 |
| Garmin Rally / Vector | o | x | o | o | ペダル型、左右バランス |
| Favero Assioma | o | x | o | o | ペダル型、左右バランス |
| SRM Origin | o | x | o | x | スパイダー型 |
| Wahoo KICKR | o | o | o | x | スマートトレーナー |
| Tacx NEO 2T | o | o | o | x | CPS + FE-C over BLE 両対応 |
| Tacx Think X2111 | o | o | o | x | CPS + FE-C over BLE |
| Elite Direto | o | x | o | x | FTMS も対応 |

※ 多くのスマートトレーナーは CPS (0x1818) と FTMS (0x1826) の両方を公開する。FE-C over BLE は Tacx 独自プロトコル。

---

## CSC (0x1816) との比較

| 項目 | CSC (0x1816) | CPS (0x1818) |
|------|-------------|-------------|
| パワーデータ | なし | **あり（常に含まれる）** |
| Flags サイズ | Uint8 (1 byte) | **Uint16 (2 bytes)** |
| ホイールタイムスタンプ解像度 | 1/1024 秒 | **1/2048 秒** |
| クランクタイムスタンプ解像度 | 1/1024 秒 | 1/1024 秒 |
| Flags ビット位置（ホイール） | bit 0 | **bit 4** |
| Flags ビット位置（クランク） | bit 1 | **bit 5** |
| ホイール回転数サイズ | Uint32 | Uint32 |
| クランク回転数サイズ | Uint16 | Uint16 |
| 追加データ | なし | トルク, バランス, 角度, エネルギー |

### 移植時の注意点

CSC のコードを CPS に流用する際の3大ハマりポイント:

1. **Flags サイズ**: Uint8 → Uint16。`getUint8(0)` を `getUint16(0, true)` に変更
2. **ホイールタイム除数**: `/ 1024` → `/ 2048`。間違えると速度が2倍ズレる
3. **オフセット計算**: Power (2 bytes) が常に Flags の直後に入るため、CSC とはオフセットが異なる。さらに Pedal Balance, Accumulated Torque がオプションで挟まる

---

## 公式仕様

- **Bluetooth SIG — GATT Specification Supplement**
  - Cycling Power Measurement: https://www.bluetooth.com/specifications/specs/gatt-specification-supplement/
  - Assigned Numbers: https://www.bluetooth.com/specifications/assigned-numbers/
- **Bluetooth SIG — Cycling Power Service (CPS) 1.1**
  - https://www.bluetooth.com/specifications/specs/cycling-power-service-1-1/
- **Bluetooth SIG — Cycling Power Profile (CPP) 1.1**
  - https://www.bluetooth.com/specifications/specs/cycling-power-profile-1-1/

## オープンソース実装・リファレンス

### JavaScript / TypeScript (Web Bluetooth)

| プロジェクト | 説明 |
|-------------|------|
| [Auuki](https://github.com/dvmarinoff/Auuki) | Web版サイクリングアプリ。`src/ble/cps/` に CPS 実装 |
| [bfree](https://github.com/bfree-trainer/bfree) | Next.js + TypeScript。`lib/ble/` に CPS 実装 |
| [WebBluetoothCPS](https://niccolorossi.github.io/AntiboticsRT/) | Web Bluetooth CPS デモ |

### Python

| プロジェクト | 説明 |
|-------------|------|
| [pycycling](https://github.com/zacharyedwardbull/pycycling) | `cycling_power_service` モジュール。全フィールド対応 |

### C++ / Arduino / ESP32

| プロジェクト | 説明 |
|-------------|------|
| [ftms_emu](https://github.com/OevreFlataeker/ftms_emu) | ESP32 で CPS をエミュレート |
| [simcline](https://github.com/Berg0162/simcline) | ESP32 で CPS/FE-C をインターセプト |
