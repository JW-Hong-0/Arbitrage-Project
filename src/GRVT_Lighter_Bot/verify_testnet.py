
import asyncio
import logging
import sys
import os

from src.GRVT_Lighter_Bot.config import Config
from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange
from src.GRVT_Lighter_Bot.utils import Utils

# Configure Logging to file and stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("verification_log.txt", encoding='utf-8')
    ]
)
logger = logging.getLogger("Verification")

async def main():
    logger.info("="*50)
    logger.info(f"🚀 GRVT-Lighter Testnet 검증 시작")
    logger.info("="*50)
    
    # 1. Config Check
    logger.info(f"[설정 확인] GRVT_ENV: {Config.GRVT_ENV}, LIGHTER_ENV: {Config.LIGHTER_ENV}")
    logger.info(f"[설정 확인] DRY_RUN: {Config.DRY_RUN} (False여야 실제 통신 가능)")
    
    if Config.DRY_RUN:
        logger.warning(f"⚠️ DRY_RUN이 True입니다. Mock 데이터가 반환될 수 있습니다.")
    
    # 2. Lighter Verification
    logger.info("\n🔵 [Lighter] 거래소 연결 테스트 중...")
    try:
        lighter = LighterExchange()
        
        # Balance
        logger.info("   👉 잔고 조회 시도...")
        balance = await lighter.get_balance()
        logger.info(f"   ✅ 잔고 조회 성공: Equity=${balance.get('equity', 0):.2f}, Available=${balance.get('available', 0):.2f}")
        
        # Ticker (via Funding Rate)
        logger.info("   👉 Ticker/Funding 조회 시도...")
        rates = await lighter.get_funding_rate("ALL")
        if rates:
            logger.info(f"   ✅ Ticker 조회 성공 (데이터 수신 완료)")
        else:
            logger.warning("   ⚠️ Ticker 데이터가 비어있습니다.")
            
        await lighter.close()
        
    except Exception as e:
        logger.error(f"   ❌ [Lighter] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    # 3. GRVT Verification
    logger.info("\n🟠 [GRVT] 거래소 연결 테스트 중...")
    try:
        grvt = GrvtExchange()
        
        # Ticker (fetch_tickers might not be supported in py-sdk so checking specific ticker)
        logger.info("   👉 Ticker(BTC_USDT_Perp) 조회 시도...")
        
        # Debug Markets
        try:
             if hasattr(grvt.client, 'markets') and grvt.client.markets:
                 keys = list(grvt.client.markets.keys())
                 logger.info(f"   ℹ️ Available Markets (First 5): {keys[:5]}")
                 if "BTC_USDT_Perp" not in keys:
                      logger.warning(f"   ⚠️ BTC_USDT_Perp not found in markets!")
        except: pass
        
        # Debug Ticker Content
        try:
             ticker = await asyncio.to_thread(grvt.client.fetch_ticker, "BTC_USDT_Perp")
             logger.info(f"   ℹ️ Raw Ticker Data: {ticker}")
        except Exception as e:
             logger.error(f"   ❌ Ticker Fetch Error: {e}")

        funding_rate = await grvt.get_funding_rate("BTC_USDT_Perp")
        
        if funding_rate is not None:
             logger.info(f"   ✅ Ticker 조회 성공 (Funding Rate: {funding_rate})")
        else:
             logger.warning("   ⚠️ Ticker 데이터 조회 실패 (None 반환)")
        
        # Balance Check
        logger.info("   👉 잔고 조회 시도...")
        balance = await grvt.get_balance()
        logger.info(f"   ✅ 잔고 조회 성공: Equity=${balance.get('equity', 0):.2f}, Available=${balance.get('available', 0):.2f}")
        
        await grvt.client.close()
        
    except Exception as e:
        logger.error(f"   ❌ [GRVT] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    logger.info("\n" + "="*50)
    logger.info("🏁 검증 절차 완료")
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(main())
