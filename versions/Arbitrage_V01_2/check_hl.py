# check_hl.py
from hyperliquid.info import Info
from hyperliquid.utils import constants

info = Info(constants.MAINNET_API_URL, skip_ws=True)
meta = info.meta()
print("=== Hyperliquid 실제 티커 명칭 목록 ===")
for asset in meta['universe']:
    print(f"Name: {asset['name']}")