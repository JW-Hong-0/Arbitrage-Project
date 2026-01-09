import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force MAINNET
os.environ["LIGHTER_ENV"] = "MAINNET"

from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange
from src.GRVT_Lighter_Bot.config import Config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def run_lighter_mainnet_test():
    logger.warning("!!! WARNING: RUNNING ON LIGHTER MAINNET !!!")
    
    lighter = LighterExchange()
    await lighter.initialize()

    # Target Symbol: 'WETH-USDC' is standard on Lighter, often mapped to 'WETH' or 'ETH'
    # Let's check available markets first
    logger.info(f"Available Symbols: {list(lighter.market_rules.keys())}")
    
    # Try to find ETH or WETH
    target_symbol = next((s for s in lighter.market_rules.keys() if 'ETH' in s), None)
    
    if not target_symbol:
        logger.error("ETH symbol not found in Lighter markets.")
        return

    logger.info(f"Target Symbol: {target_symbol}")
    
    # 1. Check Ticker & Min Qty
    logger.info("\n[STEP 1] Checking Market Info...")
    ticker_info = await lighter.get_ticker_info(target_symbol)
    logger.info(f"Ticker Info: {ticker_info}")
    
    min_qty_str = ticker_info.get('min_qty', '0.01')
    try:
        min_qty = float(min_qty_str)
    except:
        min_qty = 0.01
        
    logger.info(f"Min Qty: {min_qty}")
    
    # Check Balance
    bal = await lighter.get_balance()
    logger.info(f"Initial Balance: {bal}")
    available_usdc = bal.get('available', 0)
    logger.info(f"Available USDC: {available_usdc}")
    
    if available_usdc < 5: # Minimal check (e.g. 5 USDC)
        logger.warning(f"Balance might be too low ({available_usdc} USDC) for test.")
        # Continue anyway, let it fail at order placement if needed

    # 2. Start WebSocket (Just to verify connection)
    logger.info("\n[STEP 2] Starting WebSocket (Background)...")
    ws_task = asyncio.create_task(lighter.start_ws())
    await asyncio.sleep(3) # Wait for connect
    
    # Check Price via BBO Cache
    stats = await lighter.get_market_stats(target_symbol)
    logger.info(f"Market Stats (from WS): {stats}")
    
    current_price = stats.get('price') or stats.get('ask') or 2000.0
    logger.info(f"Estimated Price: {current_price}")

    # 3. Market Buy(Entry)
    test_qty = min_qty
    logger.info(f"\n[STEP 3] Placing Market Buy: {test_qty} {target_symbol}...")
    
    tx_hash = await lighter.place_market_order(target_symbol, 'buy', test_qty)
    
    if tx_hash:
        logger.info(f"[SUCCESS] Buy Order Sent. Hash: {tx_hash}")
        logger.info("Waiting 5s for confirmation...")
        await asyncio.sleep(5)
        
        # 4. Check Position
        logger.info("\n[STEP 4] Checking Position...")
        pos_details = await lighter.get_live_position_details(target_symbol)
        logger.info(f"Position Details: {pos_details}")
        
        size = float(pos_details.get('size', 0))
        if size > 0:
            logger.info(f"[SUCCESS] Position Verified: {size} {target_symbol}")
            
            # 5. Market Sell(Close)
            logger.info(f"\n[STEP 5] Closing Position (Market Sell)...")
            close_tx = await lighter.close_market_position(target_symbol, 'sell', size)
            
            if close_tx:
                logger.info(f"[SUCCESS] Close Order Sent. Hash: {close_tx}")
                await asyncio.sleep(5)
                
                # Check 0
                final_pos = await lighter.get_live_position_details(target_symbol)
                final_size = float(final_pos.get('size', 0))
                if final_size == 0:
                     logger.info("[SUCCESS] Position Closed Completely.")
                else:
                     logger.warning(f"[WARNING] Position remaining: {final_size}")
            else:
                logger.error("[FAIL] Close Order Failed!")
                
        else:
            logger.error("[FAIL] Position not found after Buy Order.")
    else:
        logger.error("[FAIL] Buy Order Failed!")

    await lighter.close()
    if not ws_task.done():
        ws_task.cancel()
    logger.info("\nLighter Mainnet Test Complete.")

if __name__ == "__main__":
    asyncio.run(run_lighter_mainnet_test())
