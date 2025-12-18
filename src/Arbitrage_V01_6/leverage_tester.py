import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("LevTester")

try:
    import settings
    from exchange_apis import GrvtExchange, LighterExchange
except ImportError:
    log.error("❌ exchange_apis.py가 필요합니다.")
    sys.exit(1)

async def test_leverage():
    load_dotenv()
    log.info("⚖️ 레버리지 설정 테스트 시작...\n")

    # 1. GRVT 테스트
    if os.getenv('GRVT_API_KEY'):
        log.info("🔹 [GRVT] 연결 중...")
        grvt = GrvtExchange()
        if grvt.grvt:
            target_symbol = "ETH" # 테스트할 코인
            target_lev = 10
            log.info(f"   👉 {target_symbol} 레버리지 {target_lev}배 설정 시도...")
            
            # GRVT는 심볼 뒤에 _USDT_Perp가 붙어야 함 (exchange_apis 내부에서 처리됨)
            success = await grvt.set_leverage(target_symbol, target_lev)
            if success:
                log.info(f"   ✅ [GRVT] {target_symbol} 레버리지 설정 성공!")
            else:
                log.error(f"   ❌ [GRVT] 설정 실패.")
            await grvt.close()
        else:
            log.warning("   ⚠️ GRVT 초기화 실패")
    
    print("-" * 30)

    # 2. Lighter 테스트
    if os.getenv('LIGHTER_PRIVATE_KEY'):
        log.info("🔹 [Lighter] 연결 중...")
        ltr = LighterExchange(os.getenv('LIGHTER_PRIVATE_KEY'), os.getenv('LIGHTER_WALLET_ADDRESS'))
        await ltr.load_markets() # 마켓 정보 로드 필요 (ID 매핑 위해)
        
        if ltr.is_ready:
            target_symbol = "ETH"
            target_lev = 10
            log.info(f"   👉 {target_symbol} 레버리지 {target_lev}배 설정 시도...")
            
            success = await ltr.set_leverage(target_symbol, target_lev)
            if success:
                log.info(f"   ✅ [Lighter] {target_symbol} 레버리지 설정 성공!")
            else:
                log.error(f"   ❌ [Lighter] 설정 실패.")
        else:
            log.warning("   ⚠️ Lighter 초기화 실패")

if __name__ == "__main__":
    asyncio.run(test_leverage())