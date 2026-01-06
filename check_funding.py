import asyncio
import logging
from src.GRVT_Lighter_Bot.config import Config
from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FundingChecker")

async def main():
    print("="*50)
    print("   GRVT - Lighter Funding Rate Checker")
    print("="*50)
    
    # Force LIVE mode for this check to actually hit APIs
    Config.DRY_RUN = False 
    
    # 1. Check GRVT
    print("\n[1/2] Checking GRVT API...")
    try:
        grvt = GrvtExchange()
        symbol = "BTC_USDT_Perp" # Hardcoded for test
        print(f"   Fetching {symbol}...")
        rate = await grvt.get_funding_rate(symbol)
        
        if rate is not None:
            print(f"   ✅ SUCCESS: GRVT Funding Rate = {rate:.8f}")
        else:
            print(f"   ❌ FAILED: GRVT returned None (Check Keys/Auth)")
            
    except Exception as e:
        print(f"   ❌ CRITICAL ERROR (GRVT): {e}")

    # 2. Check Lighter
    print("\n[2/2] Checking Lighter API...")
    try:
        lighter = LighterExchange()
        print(f"   Fetching All Rates...")
        rates = await lighter.get_all_tickers()
        
        if rates:
            found = False
            # Try to print first few
            print(f"   Received Data (First 3 items): {str(rates)[:200]}...")
            
            # Try to find BTC-USDT
            # Assuming list of objects or dicts
            if isinstance(rates, list):
                for r in rates:
                    # Robust attribute check
                    s = getattr(r, 'symbol', r.get('symbol') if isinstance(r, dict) else '')
                    if 'BTC' in str(s):
                        v = getattr(r, 'rate_daily', r.get('rate_daily') if isinstance(r, dict) else 0)
                        print(f"   ✅ SUCCESS: Found Lighter Rate for {s} = {v}")
                        found = True
                        break
            
            if not found:
                 print("   ⚠️ WARNING: Data received but 'BTC' symbol not found in list.")
        else:
            print(f"   ❌ FAILED: Lighter returned Empty/None")
            
    except Exception as e:
        print(f"   ❌ CRITICAL ERROR (Lighter): {e}")

    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(main())
