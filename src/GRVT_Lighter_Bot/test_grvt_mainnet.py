import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force PROD (Mainnet)
os.environ["GRVT_ENV"] = "PROD"

from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.config import Config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# --- Global Components ---
fill_event = asyncio.Event()

async def ws_fill_handler(msg):
    logger.info(f"\n[WebSocket] Msg: {msg}")
    # Check if it's a fill
    # GRVT fill msg usually has 'trade_id' or 'fill_price'
    if msg:
        logger.info("[WebSocket] Event Detected! (Possible Fill)")
        fill_event.set()

async def run_mainnet_test():
    logger.warning("!!! WARNING: RUNNING ON GRVT MAINNET !!!")
    logger.warning("Real assets will be used. Ensure XRP-USDT is selected.")
    
    grvt = GrvtExchange()
    await grvt.initialize()

    # Target: XRP-USDT
    symbol = "XRP-USDT"
    logger.info(f"Target Symbol: {symbol}")
    
    # 1. Check Min Qty & Ticker
    logger.info("[STEP 1] Checking Market Rules & Ticker...")
    try:
        # Fetch specific ticker
        grvt_symbol = "XRP_USDT_Perp"
        target_key = grvt_symbol
        
        ticker = await asyncio.to_thread(grvt.client.fetch_ticker, grvt_symbol)
        
        last_price = float(ticker.get('last') or ticker.get('last_price') or 0.0)
        best_ask = float(ticker.get('best_ask_price') or last_price)
        
        # Get Min Qty from loaded rules
        base_currency = "XRP"
        rules = grvt.market_rules.get(base_currency, {})
        min_qty = float(rules.get('min_size') or 1.0) 
        
        logger.info(f"Market: {target_key}")
        logger.info(f"Price: {last_price}, Best Ask: {best_ask}")
        logger.info(f"Min Qty: {min_qty}")
        
    except Exception as e:
        logger.error(f"Error fetching market data: {e}", exc_info=True)
        return

    # 2. Set Leverage 5x
    logger.info(f"\n[STEP 2] Setting Leverage 5x for {symbol}...")
    success = await grvt.set_leverage(symbol, 5)
    if not success:
        logger.error("Failed to set leverage. Aborting.")
        return

    # 3. Start WS
    logger.info("\n[STEP 3] Starting WebSocket...")
    ws_task = asyncio.create_task(grvt.listen_fills(ws_fill_handler))
    await asyncio.sleep(3)

    # 4. Place Limit Buy Order (Taker)
    # Buy a safe amount > 10 USD usually. If XRP is 2.5, 5 XRP is 12.5 USD.
    # Let's try 10 XRP.
    buy_qty = max(min_qty, 10.0) 
    
    # Using Best Ask to fill immediately
    buy_price = best_ask 
    
    logger.info(f"\n[STEP 4] Placing BUY Limit Order: {buy_qty} {symbol} @ {buy_price}")
    # post_only=False to allow Taker execution
    order = await grvt.place_limit_order(symbol, 'buy', buy_price, buy_qty, params={'post_only': False})
    
    if not order:
        logger.error("Order placement failed.")
        return

    logger.info(f"Order Placed: ID {order.get('id')}")

    # 5. Wait for Fill
    logger.info("\n[STEP 5] Waiting for Fill Event (20s)...")
    try:
        await asyncio.wait_for(fill_event.wait(), timeout=20)
        logger.info("[SUCCESS] Fill Event Received!")
    except asyncio.TimeoutError:
        logger.warning("No Fill Event in 20s. Order might be Pending or WS issue.")
        
    # 6. Cleanup (Close Position)
    logger.info("\n[STEP 6] Cleaning up (Selling)...")
    try:
        # Check Position first
        bal = await grvt.get_balance()
        positions = bal.get('positions', [])
        target_pos = next((p for p in positions if 'XRP' in p['symbol']), None)
        
        if target_pos:
            size = target_pos['size']
            logger.info(f"Found Position: {size} XRP. Closing...")
            # Market Sell to close
            await grvt.place_market_order(symbol, 'sell', size)
            logger.info("Close Order Placed.")
        else:
            logger.info("No Open Position found to close. monitoring order status...")
            # If order is still open, cancel it
            if order.get('id'):
                # formatting symbol for cancel might need _
                cancel_symbol = target_key # Use the key from ticker list (e.g. XRP_USDT_Perp)
                logger.info(f"Cancelling Open Order {order['id']}...")
                await asyncio.to_thread(grvt.client.cancel_order, order['id'], cancel_symbol)

    except Exception as e:
        logger.error(f"Cleanup Failed: {e}")

    await grvt.close()
    if not ws_task.done():
        ws_task.cancel()
    logger.info("\nMainnet Test Complete.")

if __name__ == "__main__":
    asyncio.run(run_mainnet_test())
