import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force TESTNET
os.environ["GRVT_ENV"] = "TESTNET"

from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.config import Config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# --- Global Validation State ---
fill_event_received = asyncio.Event()

async def ws_fill_handler(msg):
    """
    Callback for WebSocket user.trades stream.
    Expected msg structure: Check Pysdk docs or logs.
    """
    logger.info(f"\n[WebSocket] Received Message: {msg}")
    
    # Simple check: if message contains our symbol or looks like a fill
    # Adjust logic based on actual message structure
    if msg:
        logger.info("[WebSocket] Fill/Order Update Detected!")
        fill_event_received.set()

async def run_test():
    logger.info("Starting GRVT WebSocket & Limit Short Test...")
    grvt = GrvtExchange()
    await grvt.initialize()

    test_symbol = "ETH-USDT"
    
    # 1. Start WebSocket Listener in Background
    logger.info("[TEST 1] Starting WebSocket Listener...")
    ws_task = asyncio.create_task(grvt.listen_fills(ws_fill_handler))
    
    # Allow WS connection time
    await asyncio.sleep(3) 

    # 2. Get Market Price for Aggressive Limit Short
    # To ensure fill (or at least valid order), we need correct price.
    logger.info(f"\n[TEST 2] Fetching Ticker for {test_symbol}...")
    try:
        # Try explicit GRVT symbol
        grvt_symbol = "ETH_USDT_Perp"
        ticker = await asyncio.to_thread(grvt.client.fetch_ticker, grvt_symbol)
        logger.info(f"Ticker Data: {ticker}")
        # Fix: Helper to parse float safely
        def safe_float(v):
            try: return float(v)
            except: return 0.0
            
        # Check for 'last' (CCXT) or 'last_price' (GRVT Raw)
        last = ticker.get('last') or ticker.get('last_price')
        current_price = safe_float(last) if last else 2000.0
        
        logger.info(f"Current Price: {current_price}")
    except Exception as e:
        logger.error(f"Failed to fetch ticker: {e}")
        current_price = 2000.0

    # 3. Calculate Limit Price (Short at -5% of market price to simulate 'Market' via Limit)
    # Actually for Short, we want to Sell. To execute immediately, Sell Price <= Bid.
    # So if we Sell at 0.95 * Price, it should match best bid.
    limit_price = int(current_price * 0.95) 
    logger.info(f"Target Limit Sell Price: {limit_price}")

    # 4. Place Limit Short Order (Aggressive -> Post Only FALSE)
    logger.info(f"\n[TEST 3] Placing Aggressive Limit Short {test_symbol}...")
    # 10x Leverage setup just in case
    await grvt.set_leverage(test_symbol, 10)
    
    # Disable post_only to allow taking liquidity (market-like behavior)
    short_order = await grvt.place_limit_order(test_symbol, 'sell', limit_price, 0.01, params={'post_only': False})
    
    
    if short_order and short_order.get('id'):
        logger.info(f"[PASS] Order Placed: ID {short_order.get('id')}")
    else:
        logger.warning(f"[WARNING] Order Response empty or invalid: {short_order}. Checking WebSocket for confirmation...")
        # Do not return, continue to wait for WS

    # 5. Wait for WebSocket Event
    logger.info("\n[TEST 4] Waiting for WebSocket Fill Event (10s timeout)...")
    try:
        await asyncio.wait_for(fill_event_received.wait(), timeout=10)
        logger.info("[PASS] WebSocket Event Received! Real-time monitoring verified.")
    except asyncio.TimeoutError:
        logger.warning("[WARNING] No WebSocket event received in 10s. Check if Order is filled or just Pending.")
        
    # 6. Check Order Status via REST
    # Need fetch_order equivalent
    # grvt_api checks balance/positions instead
    bal = await grvt.get_balance()
    logger.info(f"Current Positions: {bal['positions']}")
    
    # 7. Cancel if open
    if short_order and short_order.get('id'):
         logger.info(f"\n[TEST 5] Cancelling Order {short_order.get('id')}...")
         try:
            grvt_symbol = test_symbol.replace("-", "_")
            await asyncio.to_thread(grvt.client.cancel_order, short_order['id'], grvt_symbol)
            logger.info("[PASS] Order Cancelled/Cleaned up.")
         except Exception as e:
            logger.warning(f"Validation Cancel: {e}")

    # Cleanup
    await grvt.close()
    if not ws_task.done():
        ws_task.cancel()
    logger.info("\nTest Sequence Complete.")

if __name__ == "__main__":
    asyncio.run(run_test())
