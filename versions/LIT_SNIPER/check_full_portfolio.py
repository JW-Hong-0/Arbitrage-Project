import logging
import os
import json
from dotenv import load_dotenv
from hyperliquid.utils import constants as hl_constants
from hyperliquid.info import Info
from eth_account import Account

# --- 설정 ---
HYENA_DEX_ID = "hyna"

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')

def check_full_portfolio():
    load_dotenv()
    
    # 1. API 키 (서명용 Agent)
    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    if not private_key:
        print("❌ .env 오류: HYPERLIQUID_PRIVATE_KEY가 없습니다.")
        return
    
    agent_account = Account.from_key(private_key)
    agent_address = agent_account.address

    # 2. 메인 주소 (조회용 Main Wallet)
    main_address = os.getenv("HYPERLIQUID_MAIN_ADDRESS")
    
    # 메인 주소가 없으면 경고 후 Agent 주소 사용 (하지만 보통 이게 원인임)
    if not main_address:
        print("\n⚠️ 경고: 'HYPERLIQUID_MAIN_ADDRESS'가 .env에 설정되지 않았습니다.")
        print(f"   현재 API 키에서 파생된 주소({agent_address})를 조회합니다.")
        print(f"   API 지갑은 보통 잔고가 0입니다. 실제 지갑 주소를 .env에 추가하세요.")
        target_address = agent_address
    else:
        target_address = main_address

    print(f"\n🔍 [자산 조회 설정]")
    print(f"   🔑 서명 지갑 (Agent): {agent_address}")
    print(f"   💰 조회 지갑 (Main) : {target_address}")
    print("="*60)

    info = Info(hl_constants.MAINNET_API_URL, skip_ws=True)

    # ---------------------------------------------------------
    # 1. Mainnet Spot 잔고 (현물 지갑)
    # ---------------------------------------------------------
    print("\n1️⃣  [Mainnet Spot] 현물 지갑 (USDC, USDe 등)")
    try:
        spot_state = info.spot_user_state(target_address)
        balances = spot_state.get('balances', [])
        
        if not balances:
            print("   - 보유한 현물 자산이 없습니다.")
        else:
            for b in balances:
                coin = b['coin']
                total = float(b['total'])
                if total > 0:
                    print(f"   • {coin:<10}: {total:,.4f}")
    except Exception as e:
        print(f"   ❌ 조회 실패: {e}")

    # ---------------------------------------------------------
    # 2. Mainnet Perpetual 잔고 (일반 선물)
    # ---------------------------------------------------------
    print("\n2️⃣  [Mainnet Perp] 일반 선물 지갑 (USDC Margin)")
    try:
        perp_state = info.user_state(target_address) # 인자 없으면 메인넷
        margin = perp_state.get('marginSummary', {})
        account_value = float(margin.get('accountValue', 0))
        withdrawable = float(margin.get('withdrawable', 0))
        
        print(f"   • 총 자산 가치 : ${account_value:,.2f}")
        print(f"   • 출금 가능 액 : ${withdrawable:,.2f}")
        
        positions = perp_state.get('assetPositions', [])
        active_pos = [p for p in positions if float(p['position']['szi']) != 0]
        if active_pos:
            print(f"   • 열린 포지션 : {len(active_pos)}개")
            for p in active_pos:
                pos = p['position']
                coin = pos['coin']
                size = float(pos['szi'])
                pnl = float(pos['unrealizedPnl'])
                leverage = pos['leverage']
                print(f"     - [{coin}] Size: {size} | PnL: ${pnl:.2f} | Lev: {leverage['type']} {leverage['value']}x")
        else:
            print("   • 열린 포지션 없음")

    except Exception as e:
        print(f"   ❌ 조회 실패: {e}")

    # ---------------------------------------------------------
    # 3. HyENA (HIP-3) 잔고 (USDe Margin)
    # ---------------------------------------------------------
    print(f"\n3️⃣  [HyENA DEX] '{HYENA_DEX_ID}' 전용 지갑")
    try:
        # HyENA DEX ID로 조회
        hyena_state = info.user_state(target_address, dex=HYENA_DEX_ID)
        margin = hyena_state.get('marginSummary', {})
        
        if margin:
            acct_val = float(margin.get('accountValue', 0))
            withd_val = float(margin.get('withdrawable', 0))
            print(f"   • 계정 가치(USDe): ${acct_val:,.2f}")
            print(f"   • 거래 가능(USDe): ${withd_val:,.2f}")
            
            positions = hyena_state.get('assetPositions', [])
            active_pos = [p for p in positions if float(p['position']['szi']) != 0]
            if active_pos:
                print(f"   • 열린 포지션 : {len(active_pos)}개")
                for p in active_pos:
                    pos = p['position']
                    print(f"     - [{pos['coin']}] Size: {pos['szi']} | PnL: ${pos['unrealizedPnl']}")
            else:
                print("   • 열린 포지션 없음")
                
        else:
            print("   ⚠️ 마진 정보가 없습니다. (HyENA 접속 기록이 없을 수 있음)")

    except Exception as e:
        print(f"   ❌ 조회 실패: {e}")

    print("="*60)

if __name__ == "__main__":
    check_full_portfolio()