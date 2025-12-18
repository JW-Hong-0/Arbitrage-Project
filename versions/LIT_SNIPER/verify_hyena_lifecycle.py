import asyncio
import logging
import os
from dotenv import load_dotenv
from hyperliquid.utils import constants as hl_constants
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange as HLExchange
from eth_account import Account

# --- 설정 ---
HYENA_DEX_ID = "hyna"
SYMBOL = "hyna:SOL"  # 정확한 티커명
TEST_SIZE_USD = 20.0 # $20
LEVERAGE = 3

HYENA_BUILDER = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
HYENA_FEE = 0

# 로깅
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger("HyENA_Lifecycle")

class HyenaLifecycleBot:
    def __init__(self):
        load_dotenv()
        self.pk = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        self.main_addr = os.getenv("HYPERLIQUID_MAIN_ADDRESS")
        
        if not self.pk:
            raise ValueError("❌ .env에 HYPERLIQUID_PRIVATE_KEY가 없습니다.")
        if not self.main_addr:
            log.warning("⚠️ .env에 HYPERLIQUID_MAIN_ADDRESS가 없습니다. 포지션 조회가 부정확할 수 있습니다.")
            self.account = Account.from_key(self.pk)
            self.main_addr = self.account.address
        else:
            self.account = Account.from_key(self.pk)

        # DEX 연결
        self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True, perp_dexs=[HYENA_DEX_ID])
        self.exchange = HLExchange(self.account, hl_constants.MAINNET_API_URL, perp_dexs=[HYENA_DEX_ID])
        self.sz_decimals = 2 # 기본값

    def load_market_info(self):
        try:
            meta = self.info.meta(dex=HYENA_DEX_ID)
            for asset in meta['universe']:
                if asset['name'] == SYMBOL:
                    self.sz_decimals = asset['szDecimals']
                    log.info(f"✅ 마켓 발견: {SYMBOL} (Decimals: {self.sz_decimals})")
                    return True
            log.error(f"❌ {SYMBOL} 마켓을 찾을 수 없습니다.")
            return False
        except Exception as e:
            log.error(f"❌ 메타데이터 로드 실패: {e}")
            return False

    async def get_current_position(self):
        """현재 포지션 수량 조회"""
        try:
            state = self.info.user_state(self.main_addr, dex=HYENA_DEX_ID)
            positions = state.get('assetPositions', [])
            for p in positions:
                pos = p.get('position', {})
                if pos.get('coin') == SYMBOL:
                    return float(pos.get('szi', 0))
            return 0.0
        except Exception as e:
            log.error(f"❌ 포지션 조회 오류: {e}")
            return 0.0

    async def execute_trade(self, side: str, size_usd: float = 0, size_token: float = 0, is_close: bool = False):
        """주문 실행 (USD 금액 또는 토큰 개수 기준)"""
        is_buy = (side == "BUY")
        
        # 1. 가격 조회
        mids = self.info.all_mids(dex=HYENA_DEX_ID)
        price = float(mids.get(SYMBOL, 0))
        if price == 0:
            log.error("❌ 가격 조회 실패")
            return False

        # 2. 수량 계산
        if size_token > 0:
            final_sz = size_token # 토큰 개수 직접 지정 (청산 시)
        else:
            raw_sz = size_usd / price
            final_sz = round(raw_sz, self.sz_decimals) # USD 환산

        if final_sz == 0:
            log.error("❌ 주문 수량이 0입니다.")
            return False

        # 3. 가격 설정 (IOC 공격적 체결)
        limit_px = float(f"{price * 1.05:.5g}") if is_buy else float(f"{price * 0.95:.5g}")

        log.info(f"🚀 {side} 주문 시도: {final_sz}개 @ ${limit_px} (현재가: ${price})")

        # 4. 전송
        req = {
            "coin": SYMBOL,
            "is_buy": is_buy,
            "sz": final_sz,
            "limit_px": limit_px,
            "order_type": {"limit": {"tif": "Ioc"}},
            "reduce_only": is_close
        }

        try:
            res = self.exchange.bulk_orders(
                [req], 
                builder={"b": HYENA_BUILDER.lower(), "f": HYENA_FEE}
            )
            
            if res['status'] == 'ok':
                status = res['response']['data']['statuses'][0]
                if 'filled' in status:
                    fill = status['filled']
                    log.info(f"✅ 체결 완료: {fill['totalSz']}개 @ ${fill['avgPx']}")
                    return float(fill['totalSz'])
                elif 'error' in status:
                    log.warning(f"⚠️ 주문 거부: {status['error']}")
            else:
                log.error(f"❌ API 응답 오류: {res}")
        except Exception as e:
            log.error(f"❌ 주문 예외 발생: {e}")
        
        return False

    async def run_lifecycle_test(self):
        if not self.load_market_info():
            return

        # 0. 초기 상태 확인
        log.info("\n--- [STEP 0] 초기 상태 확인 ---")
        initial_pos = await self.get_current_position()
        log.info(f"Initial Position: {initial_pos} {SYMBOL}")

        # 1. 레버리지 설정
        log.info("\n--- [STEP 1] 레버리지 설정 (3x) ---")
        try:
            self.exchange.update_leverage(LEVERAGE, SYMBOL, is_cross=True)
            log.info("✅ 레버리지 설정 완료")
        except Exception as e:
            log.warning(f"⚠️ 레버리지 설정 스킵 (이미 설정됨?): {e}")

        # 2. 진입 (Long)
        log.info(f"\n--- [STEP 2] 포지션 진입 (${TEST_SIZE_USD}) ---")
        filled_qty = await self.execute_trade("BUY", size_usd=TEST_SIZE_USD)
        
        if not filled_qty:
            log.error("🛑 진입 실패로 테스트 중단")
            return

        # 3. 검증
        log.info("\n--- [STEP 3] 포지션 검증 (3초 대기) ---")
        await asyncio.sleep(3)
        current_pos = await self.get_current_position()
        log.info(f"Current Position: {current_pos} {SYMBOL}")
        
        if current_pos > initial_pos:
            log.info("✅ 포지션 증가 확인됨 (진입 성공)")
        else:
            log.error("❌ 포지션 변화 없음 (체결됐으나 반영 안됨?)")
            return

        # 4. 청산 (Close)
        log.info("\n--- [STEP 4] 포지션 청산 (전량 매도) ---")
        # 현재 보유한 만큼 매도 (Reduce Only)
        # 소수점 정밀도 이슈를 피하기 위해 약간의 버퍼를 두거나 정확한 수량을 넣어야 함
        # 여기서는 조회된 current_pos를 그대로 사용
        
        # 수량이 0.0이면 청산할 게 없음
        if current_pos <= 0:
             log.warning("⚠️ 청산할 포지션이 없습니다.")
             return

        await self.execute_trade("SELL", size_token=current_pos, is_close=True)

        # 5. 최종 확인
        log.info("\n--- [STEP 5] 최종 확인 ---")
        await asyncio.sleep(2)
        final_pos = await self.get_current_position()
        log.info(f"Final Position: {final_pos} {SYMBOL}")
        
        if final_pos < current_pos:
            log.info("🎉 테스트 성공: 진입 및 청산 사이클 완료!")
        else:
            log.warning("⚠️ 청산이 완전히 이루어지지 않았을 수 있습니다.")

if __name__ == "__main__":
    bot = HyenaLifecycleBot()
    asyncio.run(bot.run_lifecycle_test())