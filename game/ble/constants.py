"""BLE で使う UUID 定数。

bleak は文字列 UUID を要求するため、128bit 形式に展開している。
0xXXXX → "0000XXXX-0000-1000-8000-00805f9b34fb" (SIG 標準UUIDの規則)
"""

def _sig_uuid(short: int) -> str:
    return f"0000{short:04x}-0000-1000-8000-00805f9b34fb"


# Cycling Speed and Cadence (CSC)
CSC_SERVICE = _sig_uuid(0x1816)
CSC_MEASUREMENT = _sig_uuid(0x2A5B)
CSC_FEATURE = _sig_uuid(0x2A5C)

# Cycling Power Service (CPS)
CPS_SERVICE = _sig_uuid(0x1818)
CPS_MEASUREMENT = _sig_uuid(0x2A63)
CPS_FEATURE = _sig_uuid(0x2A65)

# Tacx FE-C over BLE (フェーズ3以降で使用予定。今は識別のみ)
FEC_SERVICE = "6e40fec1-b5a3-f393-e0a9-e50e24dcca9e"
FEC_TX = "6e40fec2-b5a3-f393-e0a9-e50e24dcca9e"
FEC_RX = "6e40fec3-b5a3-f393-e0a9-e50e24dcca9e"
