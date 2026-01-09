import asyncio
import logging
import os
import sys

# Add project root to path for module resolution
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange
from src.GRVT_Lighter_Bot.config import Config
from src.GRVT_Lighter_Bot.utils import Utils

# --- Configuration ---
# Ensure you are in TESTNET mode in your .env file
# GRVT_ENV=TESTNET
# LIGHTER_ENV=TESTNET
# Set a test symbol and amounts
TEST_SYMBOL_GRVT = "BTC-USDT"
TEST_SYMBOL_LIGHTER = "BTC-USDT" # Changed to BTC-USDT to test valid market index
LEVERAGE_GRVT = 10
LEVERAGE_LIGHTER = 5
ORDER_AMOUNT_GRVT = 0.001
ORDER_AMOUNT_LIGHTER = 0.001
# For GRVT limit order test
LIMIT_PRICE_OFFSET_BPS = 50 # Place limit order 0.5% away from market price


# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def test_grvt_functionality(grvt: GrvtExchange):
    """Tests GRVT leverage, order placement, and cancellation."""
    logger.info("\n" + "="*30 + " TESTING GRVT " + "="*30)

    # 1. Check Balance
    logger.info("\n--- 1. Fetching GRVT Balance ---")
    balance = await grvt.get_balance()
    if balance:
        logger.info(f"GRVT Balance: {balance}")
    else:
        logger.error("Could not fetch GRVT balance.")
        return

    # 2. Set Leverage
    logger.info(f"\n--- 2. Setting GRVT Leverage for {TEST_SYMBOL_GRVT} to {LEVERAGE_GRVT}x ---")
    success = await grvt.set_leverage(TEST_SYMBOL_GRVT, LEVERAGE_GRVT)
    if not success:
        logger.error("Failed to set GRVT leverage.")
        # Continue anyway to test other things

    # 3. Verify Leverage
    logger.info("\n--- 3. Verifying GRVT Leverage ---")
    ticker_info = await grvt.get_ticker_info(TEST_SYMBOL_GRVT)
    if ticker_info:
        logger.info(f"GRVT Ticker Info for {TEST_SYMBOL_GRVT}: {ticker_info}")
        current_lev = ticker_info.get('current_leverage')
        if current_lev and float(current_lev) == float(LEVERAGE_GRVT):
            logger.info(f"✅ Leverage verification successful: Current is {current_lev}x.")
        else:
            logger.warning(f"⚠️ Leverage verification failed or mismatch. Expected: {LEVERAGE_GRVT}, Got: {current_lev}")
    else:
        logger.error("Could not get GRVT ticker info to verify leverage.")

    # 4. Place Market Order
    logger.info(f"\n--- 4. Placing GRVT Market Buy Order for {ORDER_AMOUNT_GRVT} {TEST_SYMBOL_GRVT} ---")
    market_order = await grvt.place_market_order(TEST_SYMBOL_GRVT, 'buy', ORDER_AMOUNT_GRVT)
    if market_order and market_order.get('id'): # Check for 'id' key for robustness
        logger.info(f"✅ Market order placed successfully: {market_order}")
    else:
        logger.error("Failed to place GRVT market order.")

    # Give time for the order to affect balance
    await asyncio.sleep(5)
    balance_after_buy = await grvt.get_balance()
    logger.info(f"Balance after market buy: {balance_after_buy}")

    # 5. Place Limit Order
    logger.info(f"\n--- 5. Placing GRVT Limit Sell Order ---")
    try:
        # Fetch current price to place order away from it
        ticker = await asyncio.to_thread(grvt.client.fetch_ticker, Utils.to_grvt_symbol(TEST_SYMBOL_GRVT))
        last_price = ticker.get('last_price')
        if not last_price:
            raise ValueError("Could not fetch last price to place a limit order.")
        
        limit_price = float(last_price) * (1 + LIMIT_PRICE_OFFSET_BPS / 10000)
        
        limit_order = await grvt.place_limit_order(TEST_SYMBOL_GRVT, 'sell', limit_price, ORDER_AMOUNT_GRVT)
        if limit_order:
            logger.info(f"✅ Limit order placed successfully: {limit_order}")
            order_id = limit_order.get('id')

            # 6. Cancel Limit Order
            if order_id:
                logger.info(f"\n--- 6. Cancelling GRVT Limit Order ID: {order_id} ---")
                # CCXT uses 'cancel_order'
                cancellation = await asyncio.to_thread(grvt.client.cancel_order, order_id, Utils.to_grvt_symbol(TEST_SYMBOL_GRVT))
                logger.info(f"✅ Cancellation response: {cancellation}")
        else:
            logger.error("Failed to place GRVT limit order.")
    except Exception as e:
        logger.error(f"An error occurred during limit order placement/cancellation: {e}", exc_info=True)


async def test_lighter_functionality(lighter: LighterExchange):
    """Tests Lighter leverage and order placement."""
    logger.info("\n" + "="*30 + " TESTING LIGHTER " + "="*30)
    
    # 1. Check Balance
    logger.info("\n--- 1. Fetching Lighter Balance ---")
    balance = await lighter.get_balance()
    if balance and balance.get('equity') > 0:
        logger.info(f"Lighter Balance: {balance}")
    else:
        logger.error("Could not fetch Lighter balance or balance is zero. Make sure wallet is funded on testnet.")
        return

    # 2. Set Leverage
    logger.info(f"\n--- 2. Setting Lighter Leverage for {TEST_SYMBOL_LIGHTER} to {LEVERAGE_LIGHTER}x ---")
    # Using 'isolated' for Lighter as it's often safer for single-position tests
    success = await lighter.set_leverage(TEST_SYMBOL_LIGHTER, LEVERAGE_LIGHTER, 'isolated')
    if not success:
        logger.error("Failed to submit Lighter leverage update.")
        # Continue anyway

    # 3. Verify Leverage
    logger.info("\n--- 3. Verifying Lighter Leverage ---")
    # Verification is implicit. The API call for setting leverage either succeeds or fails on submission.
    # We can fetch ticker info to see what the *max* leverage is, but not current position leverage without a position.
    ticker_info = await lighter.get_ticker_info(TEST_SYMBOL_LIGHTER)
    if ticker_info:
        logger.info(f"Lighter Ticker Info for {TEST_SYMBOL_LIGHTER}: {ticker_info}")
    else:
        logger.error("Could not get Lighter ticker info.")

    # 4. Place Market Order
    logger.info(f"\n--- 4. Placing Lighter Market Buy Order for {ORDER_AMOUNT_LIGHTER} {TEST_SYMBOL_LIGHTER} ---")
    market_order_hash = await lighter.place_market_order(TEST_SYMBOL_LIGHTER, 'buy', ORDER_AMOUNT_LIGHTER)
    if market_order_hash:
        logger.info(f"✅ Market order submitted successfully. Transaction Hash: {market_order_hash}")
    else:
        logger.error("Failed to place Lighter market order.")
        
    # Give time for the order to affect balance
    logger.info("Waiting 10 seconds for Lighter transaction to be processed...")
    await asyncio.sleep(10)
    balance_after_buy = await lighter.get_balance()
    logger.info(f"Balance after market buy: {balance_after_buy}")



async def main():
    """Main function to run the verification tests."""
    logger.info("Starting exchange functionality verification script...")
    
    # Initialize exchanges
    grvt = GrvtExchange()
    lighter = LighterExchange()
    
    await grvt.initialize()
    await lighter.initialize()

    # Run tests
    await test_grvt_functionality(grvt)
    await test_lighter_functionality(lighter)

    logger.info("\nVerification script finished.")


if __name__ == "__main__":
    # Ensure the environment is set to TESTNET for safety
    if Config.GRVT_ENV != "TESTNET" or Config.LIGHTER_ENV != "TESTNET":
        logger.error("="*50)
        logger.error("!!! SAFETY ERROR !!!")
        logger.error("This script is intended for TESTNET ONLY.")
        logger.error(f"Current GRVT_ENV: {Config.GRVT_ENV}, Current LIGHTER_ENV: {Config.LIGHTER_ENV}")
        logger.error("Please set both to 'TESTNET' in your .env file to proceed.")
        logger.error("="*50)
    else:
        asyncio.run(main())
