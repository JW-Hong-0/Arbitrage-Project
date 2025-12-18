import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from hyperliquid.utils import constants as hl_constants
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange as HLExchange
from eth_account import Account

# --- [설정 섹션] ---
# 1. 찾은 DEX ID (Name) 적용
HYENA_DEX_ID = "hyna"  

# 2. HyENA 포인트 적립을 위한 빌더 정보 (필수)
HYENA_BUILDER_ADDRESS = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
HYENA_BUILDER_FEE = 0

# 3. 테스트 타겟 설정
TEST_SYMBOL = "SOL"
TEST_LEVERAGE = 3
TEST_POSITION_VALUE_USD = 20.0  # $20 어치 (레버리지 포함 명목 가치)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("HyENA_Verifier")

class HyenaVerifier:
    def __init__(self, private_key: str):
        self.account = Account.from_key(private_key)
        self.main_address = self.account.address
        self.sz_decimals = {} 
        
        try:
            log.info(f"🔌 HyENA DEX 연결 시도 (ID: {HYENA_DEX_ID})...")
            
            # [핵심] Info와 Exchange 객체에 perp_dexs 리스트를 전달하여 HIP-3 모드 활성화
            # SDK는 이 리스트를 통해 메인넷(0번)과 HyENA(hyna)를 구분합니다.
            self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True, perp_dexs=[HYENA_DEX_ID])
            
            self.exchange = HLExchange(
                self.account, 
                hl_constants.MAINNET_API_URL, 
                perp_dexs=[HYENA_DEX_ID] 
            )
            
            # 연결 확인 및 자산 정보 로드
            self._load_market_meta()
            log.info(f"✅ 초기화 완료. 지갑: {self.main_address[:8]}...")
            
        except Exception as e:
            log.error(f"❌ 초기화 실패: {e}")
            raise e

    def _load_market_meta(self):
        """HyENA 마켓의 소수점 자릿수(Precision) 정보 로드"""
        try:
            # perp_dexs 설정을 했으므로 sdk가 자동으로 처리해주길 기대하지만,
            # 명시적으로 dex 옵션을 주는 것이 안전함
            meta = self.info.meta(dex=HYENA_DEX_ID)
            for asset in meta['universe']:
                self.sz_decimals[asset['name']] = asset['szDecimals']
            
            if TEST_SYMBOL in self.sz_decimals:
                log.info(f"🔍 마켓 정보 로드: {TEST_SYMBOL} (Decimals: {self.sz_decimals[TEST_SYMBOL]})")
            else:
                log.warning(f"⚠️ {TEST_SYMBOL} 마켓을 HyENA에서 찾을 수 없습니다.")
                
        except Exception as e:
            log.error(f"⚠️ 마켓 메타데이터 로드 실패: {e}")

    async def check_balance(self):
        """USDe 증거금 잔고 확인"""
        try:
            # dex=HYENA_DEX_ID 파라미터 필수
            state = self.info.user_state(self.main_address, dex=HYENA_DEX_ID)
            margin = state.get('marginSummary', {})
            
            equity = float(margin.get('accountValue', 0))
            withdrawable = float(margin.get('withdrawable', 0))
            
            log.info(f"💰 [USDe 잔고] 총 자산: ${equity:.2f} | 출금 가능: ${withdrawable:.2f}")
            
            if withdrawable < (TEST_POSITION_VALUE_USD / TEST_LEVERAGE):
                log.warning("⚠️ 주의: 잔고가 테스트 주문 금액보다 적을 수 있습니다.")
                
            return equity
        except Exception as e:
            log.error(f"❌ 잔고 조회 실패: {e}")
            return 0.0

    async def set_leverage(self):
        """레버리지 설정 (3배)"""
        try:
            log.info(f"⚙️ {TEST_SYMBOL} 레버리지 {TEST_LEVERAGE}x 설정 시도...")
            
            # update_leverage 함수 사용 (Exchange 클래스 내장)
            # SDK가 perp_dexs 컨텍스트를 사용하여 해당 DEX로 요청을 보냄
            res = self.exchange.update_leverage(TEST_LEVERAGE, TEST_SYMBOL, is_cross=True)
            
            if res['status'] == 'ok':
                log.info(f"✅ 레버리지 설정 성공")
            else:
                log.error(f"❌ 레버리지 설정 응답 오류: {res}")
                
        except Exception as e:
            log.error(f"❌ 레버리지 설정 실패: {e}")

    async def place_test_order(self):
        """주문 실행 (시장가 매수 효과)"""
        # 1. 현재가 조회
        all_mids = self.info.all_mids(dex=HYENA_DEX_ID)
        price = float(all_mids.get(TEST_SYMBOL, 0))
        
        if price == 0:
            log.error("❌ 가격 데이터 수신 실패 (0 USD)")
            return

        # 2. 수량 계산 (목표가치 $20 / 현재가)
        raw_amount = TEST_POSITION_VALUE_USD / price
        
        # 정밀도 보정
        decimals = self.sz_decimals.get(TEST_SYMBOL, 2)
        amount = round(raw_amount, decimals)
        
        log.info(f"📊 주문 계산: 현재가 ${price} | 목표 ${TEST_POSITION_VALUE_USD} | 수량 {amount} {TEST_SYMBOL}")

        if amount == 0:
            log.error("❌ 주문 수량이 0입니다. 금액을 늘리세요.")
            return

        # 3. 주문 전송 (IOC, 현재가보다 5% 높게)
        limit_px = float(f"{price * 1.05:.5g}")
        
        order_req = {
            "coin": TEST_SYMBOL,
            "is_buy": True,
            "sz": amount,
            "limit_px": limit_px,
            "order_type": {"limit": {"tif": "Ioc"}},
            "reduce_only": False
        }

        try:
            log.info("🚀 주문 전송 중...")
            res = self.exchange.bulk_orders(
                [order_req],
                builder={"b": HYENA_BUILDER_ADDRESS.lower(), "f": HYENA_BUILDER_FEE}
            )
            
            status = res['status']
            if status == 'ok':
                statuses = res['response']['data']['statuses']
                first_status = statuses[0]
                
                if 'filled' in first_status:
                    fill = first_status['filled']
                    log.info(f"🎉 체결 성공! {fill['totalSz']} {TEST_SYMBOL} @ ${fill['avgPx']}")
                    log.info("ℹ️ 포지션이 생성되었습니다. HLP/HyENA 페이지에서 확인하세요.")
                elif 'error' in first_status:
                    log.warning(f"⚠️ 주문 거부됨: {first_status['error']}")
            else:
                log.error(f"❌ API 응답 오류: {res}")
                
        except Exception as e:
            log.error(f"❌ 주문 실행 중 예외 발생: {e}")

# --- 메인 실행부 ---
async def main():
    load_dotenv()
    pk = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    
    if not pk:
        print("❌ .env 파일 확인 필요")
        return

    bot = HyenaVerifier(pk)
    
    print("\n--- [STEP 1] 잔고 확인 ---")
    await bot.check_balance()
    
    print("\n--- [STEP 2] 레버리지 설정 ---")
    await bot.set_leverage()
    
    print("\n--- [STEP 3] 주문 실행 (3초 대기) ---")
    await asyncio.sleep(3)
    await bot.place_test_order()

if __name__ == "__main__":
    asyncio.run(main())