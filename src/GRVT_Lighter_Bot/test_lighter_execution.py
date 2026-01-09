import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange
from src.GRVT_Lighter_Bot.config import Config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def run_test():
    if Config.LIGHTER_ENV != "TESTNET":
        logger.error("This test must be run on TESTNET.")
        return

    logger.info("Starting Lighter Execution Test...")
    lighter = LighterExchange()
    await lighter.initialize()

    test_symbol = "ETH-USDT"
    test_qty = 0.001

    async def get_details():
        return await lighter.get_live_position_details(test_symbol)

    async def print_position_details(label):
        details = await get_details()
        logger.info(f"--- {label} ---")
        logger.info(f"Size: {details['size']} (Sign included)")
        logger.info(f"Entry Price: {details['entry_price']}")
        logger.info(f"Leverage: {details['leverage']}x")
        logger.info(f"Margin Used: {details['margin_used']}")
        logger.info(f"Unrealized PnL: {details['unrealized_pnl']}")
        logger.info(f"Funding Rate: {details['funding_rate']}")
        logger.info("-----------------------")
        return details

    async def cleanup_position():
        logger.info("[Cleanup] Checking execution for existing positions to close...")
        
        for i in range(5): # Retry up to 5 times
            details = await get_details()
            size = details['size']
            
            if size == 0:
                logger.info(f"[Cleanup] No Position found. Clean state. (Attempt {i+1})")
                return True
            
            # Format size to avoid floating point artifacts (e.g. 1e-10)
            if abs(size) < 0.0001: # Assume 0 if very small
                 logger.info(f"[Cleanup] Position size {size} is negligible. Considering clean.")
                 return True

            logger.info(f"[Cleanup] Found existing position: {size}. Closing... (Attempt {i+1})")
            
            # Determine side to close
            side = 'sell' if size > 0 else 'buy'
            abs_size = abs(size)
            
            # Use close_market_position logic (Reduce-Only)
            tx = await lighter.close_market_position(test_symbol, side, abs_size)
            
            if tx:
                logger.info(f"[Cleanup] Close order placed. Waiting for fill...")
                await asyncio.sleep(4) # Increased wait time
            else:
                logger.error("[Cleanup] Failed to place close order.")
                await asyncio.sleep(1)
        
        # Final Check
        details = await get_details()
        if details['size'] == 0:
             return True
        else:
             logger.error(f"[Cleanup] Failed to clean position after 5 attempts. Size: {details['size']}")
             return False

    # --- Scenario 1: 1x Long ---
    logger.info("\n=== [Scenario 1] 1x Long Strategy ===")
    
    # 0. Cleanup
    if not await cleanup_position():
        logger.error("[Start] Initial Cleanup Failed. Aborting Test.")
        return

    # 1. Set Leverage 1x
    logger.info("[1.1] Setting Leverage to 1x...")
    await lighter.set_leverage(test_symbol, 1, 'cross')

    # 2. Open Long
    logger.info(f"[1.2] Opening Long {test_qty} {test_symbol}...")
    await lighter.place_market_order(test_symbol, 'buy', test_qty)

    await asyncio.sleep(2) # Wait for fill
    pos = await print_position_details("Post-Entry Position (1x Long)")
    
    if pos['size'] > 0: logger.info("[Verify] [PASS] Position size is positive (Long).")
    else: logger.error(f"[Verify] [FAIL] Position size mismatch: {pos['size']}")

    # 3. Close Position
    logger.info("[1.3] Closing Position...")
    await cleanup_position()


    # --- Scenario 2: 3x Long ---
    logger.info("\n=== [Scenario 2] 3x Long Strategy ===")
    
    # 0. Cleanup
    if not await cleanup_position():
         logger.error("Cleanup failed before Scenario 2. Skipping.")
    else:
        # 1. Set Leverage 3x
        logger.info("[2.1] Setting Leverage to 3x...")
        await lighter.set_leverage(test_symbol, 3, 'cross')

        # 2. Open Long
        logger.info(f"[2.2] Opening Long {test_qty} {test_symbol}...")
        await lighter.place_market_order(test_symbol, 'buy', test_qty)

        await asyncio.sleep(2)
        pos = await print_position_details("Post-Entry Position (3x Long)")
        
        if pos['size'] > 0: logger.info("[Verify] [PASS] Position size is positive (Long).")
        else: logger.error(f"[Verify] [FAIL] Position size mismatch: {pos['size']}")

        # 3. Close Position
        logger.info("[2.3] Closing Position...")
        await cleanup_position()


    # --- Scenario 3: 3x Short ---
    logger.info("\n=== [Scenario 3] 3x Short Strategy ===")
    
    # 0. Cleanup
    if not await cleanup_position():
         logger.error("Cleanup failed before Scenario 3. Skipping.")
    else:
        # 1. Set Leverage 3x
        logger.info("[3.1] Ensuring Leverage is 3x...")
        await lighter.set_leverage(test_symbol, 3, 'cross')

        # 2. Open Short
        logger.info(f"[3.2] Opening Short {test_qty} {test_symbol}...")
        await lighter.place_market_order(test_symbol, 'sell', test_qty)

        await asyncio.sleep(2)
        pos = await print_position_details("Post-Entry Position (3x Short)")

        if pos['size'] < 0: logger.info("[Verify] [PASS] Position size is negative (Short).")
        else: logger.error(f"[Verify] [FAIL] Position size mismatch: {pos['size']} (Expected Negative)")

        # 3. Close Position
        logger.info("[3.3] Closing Position...")
        await cleanup_position()

    await lighter.close()
    logger.info("\n=== All Scenarios Complete ===")

if __name__ == "__main__":
    asyncio.run(run_test())
