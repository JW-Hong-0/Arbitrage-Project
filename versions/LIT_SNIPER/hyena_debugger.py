import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from hyperliquid.utils import constants as hl_constants
from hyperliquid.info import Info
from eth_account import Account

# --- 설정 ---
HYENA_DEX_ID = "hyna"  # 찾으신 DEX ID

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("Debugger")

def print_json(data, label):
    print(f"\n--- [ {label} ] ---")
    print(json.dumps(data, indent=2))

def debug_hyena():
    load_dotenv()
    pk = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    if not pk:
        print("❌ .env 파일이 없거나 HYPERLIQUID_PRIVATE_KEY가 비어있습니다.")
        return

    account = Account.from_key(pk)
    address = account.address
    print(f"🔍 디버깅 시작 (지갑: {address})")
    print(f"🎯 대상 DEX: {HYENA_DEX_ID}")

    # 1. Info 객체 생성 (DEX 연결)
    try:
        info = Info(hl_constants.MAINNET_API_URL, skip_ws=True, perp_dexs=[HYENA_DEX_ID])
        print("✅ Info 객체 초기화 성공")
    except Exception as e:
        print(f"❌ Info 초기화 실패: {e}")
        return

    # 2. HyENA 메타데이터 조회 (상장된 코인 목록 확인)
    try:
        print("\n⏳ HyENA 마켓 데이터(Meta) 조회 중...")
        meta = info.meta(dex=HYENA_DEX_ID)
        
        print(f"📋 총 {len(meta['universe'])}개의 자산 발견:")
        for idx, asset in enumerate(meta['universe']):
            # 자산의 정확한 이름과 설정 출력
            print(f"   [{idx}] Name: '{asset['name']}' | Decimals: {asset['szDecimals']} | MaxLev: {asset['maxLeverage']}")
            
    except Exception as e:
        print(f"❌ 메타데이터 조회 실패: {e}")

    # 3. 가격 데이터 조회
    try:
        print("\n⏳ 현재가(All Mids) 조회 중...")
        mids = info.all_mids(dex=HYENA_DEX_ID)
        if not mids:
            print("⚠️ 가격 데이터가 비어있습니다 (아직 거래 전일 수 있음)")
        else:
            print(f"💲 수신된 가격 데이터: {mids}")
    except Exception as e:
        print(f"❌ 가격 조회 실패: {e}")

    # 4. 잔고 정밀 진단
    print("\n💰 [잔고 정밀 진단]")
    
    # 4-1. Spot 잔고 (지갑에 보유한 실제 토큰)
    try:
        spot_state = info.spot_user_state(address)
        spot_balances = spot_state.get('balances', [])
        print("\n   [1] Mainnet Spot 잔고 (내 지갑):")
        found_usde = False
        for b in spot_balances:
            if float(b['total']) > 0:
                print(f"       - {b['coin']}: {b['total']}")
            if b['coin'] == 'USDe': # USDe 확인
                found_usde = True
        
        if not found_usde:
            print("       ⚠️ 지갑에 'USDe' 토큰이 보이지 않습니다.")
            
    except Exception as e:
        print(f"❌ Spot 잔고 조회 실패: {e}")

    # 4-2. HyENA DEX 잔고 (마진으로 예치된 금액)
    try:
        dex_state = info.user_state(address, dex=HYENA_DEX_ID)
        margin = dex_state.get('marginSummary', {})
        print("\n   [2] HyENA DEX 내부 잔고 (Margin):")
        print(f"       - Account Value: {margin.get('accountValue')}")
        print(f"       - Withdrawable:  {margin.get('withdrawable')}")
        
        # 포지션 확인
        positions = dex_state.get('assetPositions', [])
        if positions:
            print(f"       - 열려있는 포지션: {len(positions)}개")
            for p in positions:
                pos = p.get('position', {})
                print(f"         > {pos.get('coin')}: Size={pos.get('szi')} PnL={pos.get('unrealizedPnl')}")
        else:
            print("       - 열려있는 포지션 없음")

    except Exception as e:
        print(f"❌ HyENA 상태 조회 실패: {e}")

if __name__ == "__main__":
    debug_hyena()