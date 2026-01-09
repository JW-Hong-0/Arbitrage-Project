import asyncio
import logging
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force PROD
os.environ["GRVT_ENV"] = "PROD"

from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_full_cycle():
    logger.warning("!!! STARTING GRVT MAINNET FULL CYCLE TEST !!!")
    grvt = GrvtExchange()
    await grvt.initialize()
    
    symbol = "XRP-USDT"
    
    # 0. Prep: Get Market Data
    logger.info("Fetching Market Data...")
    try:
        grvt_symbol = "XRP_USDT_Perp"
        ticker = await asyncio.to_thread(grvt.client.fetch_ticker, grvt_symbol)
        
        # Safe float parsing
        def safe_float(v):
            try: return float(v)
            except: return 0.0
            
        last_price = safe_float(ticker.get('last') or ticker.get('last_price') or 2.0)
        logger.info(f"Current Price: {last_price}")
        
        # Min Qty
        base_currency = "XRP"
        rules = grvt.market_rules.get(base_currency, {})
        min_qty = float(rules.get('min_size') or 10.0)
        logger.info(f"Min Qty: {min_qty}")
        
        test_qty = min_qty # Use exact min qty
        
    except Exception as e:
        logger.error(f"Failed Prep: {e}")
        return

    # --- TEST 1: Limit Order Cancellation ---
    logger.info("\n--- TEST 1: Limit Order Cancel ---")
    limit_price = last_price * 0.5 # Deep OTM
    logger.info(f"Placing Limit Buy @ {limit_price} (Should not fill)")
    
    order = await grvt.place_limit_order(symbol, 'buy', limit_price, test_qty)
    
    if order and order.get('id') and order.get('id') != '0x00':
        logger.info(f"Order Placed: {order.get('id')}")
        await asyncio.sleep(2)
        
        logger.info("Cancelling Order...")
        try:
             # Use proper symbol for cancel if needed
             # SDK might need grvt_symbol
             c_res = await asyncio.to_thread(grvt.client.cancel_order, order['id'], grvt_symbol)
             logger.info(f"[SUCCESS] Order Cancelled. Result: {c_res}")
        except Exception as e:
            logger.error(f"[FAIL] Cancel Failed: {e}")
    else:
        logger.error(f"[SKIP] Limit Order Failed or Invalid ID: {order}")

    # --- TEST 2: Market Buy & Position Check ---
    logger.info("\n--- TEST 2: Market Buy (Entry) ---")
    logger.info(f"Buying {test_qty} XRP at Market...")
    
    buy_order = await grvt.place_market_order(symbol, 'buy', test_qty)
    
    if not buy_order:
        logger.error("[FAIL] Market Buy Failed")
        return

    logger.info("Waiting 5s for fill/position update...")
    await asyncio.sleep(5)
    
    # Check Position
    bal = await grvt.get_balance()
    messages = bal.get('info', {}).get('msg', 'No info') 
    positions = bal.get('positions', [])
    logger.info(f"Balance Positions: {positions}")
    
    xrp_pos = next((p for p in positions if p.get('symbol') and 'XRP' in p['symbol']), None)
    
    if xrp_pos and float(xrp_pos['size']) > 0:
        size = float(xrp_pos['size'])
        logger.info(f"[SUCCESS] Position Found: {size} XRP")
        
        # --- TEST 3: Market Sell (Close) ---
        logger.info("\n--- TEST 3: Market Sell (Close) ---")
        logger.info(f"Selling {size} XRP at Market...")
        
        sell_order = await grvt.place_market_order(symbol, 'sell', size)
        if sell_order:
             logger.info("Sell Order Placed. Waiting 5s...")
             await asyncio.sleep(5)
             
             # Re-check
             bal_final = await grvt.get_balance()
             pos_final = next((p for p in bal_final.get('positions', []) if 'XRP' in p['symbol']), None)
             
             if not pos_final or float(pos_final['size']) == 0:
                 logger.info("[SUCCESS] Position Closed Completely.")
             else:
                 logger.warning(f"[WARNING] Position still exists: {pos_final}")
        else:
            logger.error("[FAIL] Sell Order Failed!")
            
    else:
        logger.error(f"[FAIL] No Position Found! Order: {buy_order}")
        
        # Check Open Orders
        try:
             logger.info("Checking Open Orders...")
             # SDK fetch_open_orders might not be available, try cancel blindly or skip
             # Best effort: use the Buy Order ID if it exists
             if buy_order.get('id') and buy_order.get('id') != '0x00':
                 await asyncio.to_thread(grvt.client.cancel_order, buy_order['id'], grvt_symbol)
                 logger.info("Cancelled Buy Order.")
             else:
                 logger.warning("Cannot cancel Buy Order: ID is 0x00. Please check GRVT Dashboard manually.")
        except Exception as e:
             logger.error(f"Error checking open orders: {e}")

    await grvt.close()
    logger.info("\nFull Cycle Test Complete.")

if __name__ == "__main__":
    asyncio.run(run_full_cycle())
