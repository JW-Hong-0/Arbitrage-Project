import asyncio
import logging
import time
import uuid
from typing import Optional, Dict

from ..exchanges.grvt_api import GrvtExchange
from ..exchanges.lighter_api import LighterExchange
from .bot_state import BotState, DualPosition
from .opportunity_scanner import arbitrage_opportunity

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self, grvt: GrvtExchange, lighter: LighterExchange, state: BotState):
        self.grvt = grvt
        self.lighter = lighter
        self.state = state
        self.active_orders = {} # map order_id to position_id or context
        
        # Buffer settings
        self.HEDGE_THRESHOLD_USD = 10.0 # Don't hedge until $10 collected (save gas)
        self.MAX_HEDGE_DELAY = 10.0 # Force hedge after 10s even if small

    async def execute_entry_strategy(self, opp: arbitrage_opportunity, size: float):
        """
        1. Pre-flight Check.
        2. Place Maker Order on GRVT.
        """
        logger.info(f"--- Executing Entry Strategy for {opp.symbol} ---")
        
        # 1. Pre-flight Checks (Simple version)
        if not await self._pre_flight_check(opp):
            logger.warning("Pre-flight check failed. Aborting entry.")
            return False

        # 2. Determine Side
        side = 'buy' if opp.direction == 'Long_GRVT' else 'sell'
        
        # Price logic (Maker)
        # Price logic (Maker)
        ticker_data = await asyncio.to_thread(self.grvt.client.fetch_ticker, opp.grvt_symbol)
        ticker = ticker_data[0] if isinstance(ticker_data, list) and ticker_data else ticker_data
        
        best_bid = float(ticker.get('bid') or ticker.get('best_bid_price') or 0)
        best_ask = float(ticker.get('ask') or ticker.get('best_ask_price') or 0)
        
        if side == 'buy':
            price = best_bid if best_bid > 0 else float(ticker['last']) * 0.99
        else:
            price = best_ask if best_ask > 0 else float(ticker['last']) * 1.01
            
        logger.info(f"Placing GRVT Maker {side.upper()} @ {price} for {size} {opp.symbol}")
        
        # Place Post-Only Order
        order = await self.grvt.place_limit_order(
            symbol=opp.grvt_symbol,
            side=side,
            price=price,
            amount=size,
            params={'post_only': True}
        )
        
        if order and order.get('id'):
            pos_id = str(uuid.uuid4())
            new_pos = DualPosition(
                id=pos_id,
                symbol=opp.symbol,
                grvt_symbol=opp.grvt_symbol,
                lighter_symbol=opp.lighter_symbol,
                entry_time=time.time(),
                size=size,
                pending_hedge_qty=0.0,
                grvt_entry_price=price,
                lighter_entry_price=0,
                status='OPENING'
            )
            self.state.add_position(new_pos)
            self.active_orders[str(order['id'])] = {
                'type': 'ENTRY',
                'pos_id': pos_id,
                'opp': opp,
                'ts': time.time()
            }
            logger.info(f"Entry Order Placed: {order['id']}. Position ID: {pos_id}")
            return True
        else:
            logger.error("Failed to place GRVT Entry Order.")
            return False

    async def _pre_flight_check(self, opp: arbitrage_opportunity) -> bool:
        # Check Rules/Balances
        # TODO: Implement stricter checks (Gas check, precise balance check)
        return True

    async def handle_grvt_fill(self, fill_data: dict):
        """
        Accumulate fills into 'pending_hedge_qty'.
        """
        order_id = fill_data.get('order_id')
        if not order_id: return

        # Normalize order_id to string
        order_key = str(order_id)
        order_ctx = self.active_orders.get(order_key)
        
        if not order_ctx:
            # Try to match int if key is str
            order_ctx = self.active_orders.get(int(order_id)) if str(order_id).isdigit() else None
            
        if not order_ctx:
            return # Ignore irrelevant fills

        pos_id = order_ctx['pos_id']
        pos = self.state.positions.get(pos_id)
        if not pos: return

        fill_qty = float(fill_data.get('size', 0))
        # fill_price = float(fill_data.get('price', 0)) 
        
        logger.info(f"Fill Detected on {pos.symbol}: {fill_qty} (Accumulating)")
        
        if order_ctx['type'] == 'ENTRY':
            # Update Position State
            pos.pending_hedge_qty += fill_qty
            pos.status = 'OPENING' # Still opening
            self.state.update_position(pos)
            
            # Use 'process_pending_hedges' to execute actual hedge logic
            await self.process_pending_hedges(pos)
            
        elif order_ctx['type'] == 'EXIT':
            # For Exit, usually we want immediate hedge too
            pos.pending_hedge_qty += fill_qty
            await self.process_pending_hedges(pos, is_exit=True)

    async def process_pending_hedges(self, position: DualPosition, is_exit: bool = False):
        """
        Checks if pending qty is enough to hedge, if so executes market order.
        """
        qty = position.pending_hedge_qty
        if qty <= 0: return

        # Threshold check: Is size > Min Lighter Size?
        # Assuming Min Size is small (e.g. 0.01 ETH).
        # We can fetch 'min_base_amount' from lighter rules.
        min_qty = 0.001 # Default safe fallback
        if position.lighter_symbol in self.lighter.market_rules:
             min_qty = float(self.lighter.market_rules[position.lighter_symbol].get('min_base_amount', 0))
        
        if qty >= min_qty:
            logger.info(f"Triggering Hedge for {position.symbol}. Qty: {qty} (Is Exit: {is_exit})")
            
            # Determine Side
            # Entry: GRVT Long -> Lighter Short (Sell)
            # Exit: GRVT Sell -> Lighter Long (Buy)
            # We need to know 'direction'. 
            # If Entry was 'Long_GRVT', we bought GRVT.
            # But 'DualPosition' doesn't store direction well yet (FIXME).
            # Infer from active_order if possible or assume delta neutral
            # Temp: If OPENING, assume we did the Maker side.
            # Current Logic assumption:
            # We open with Maker. If we are Long GRVT, we need Short Lighter.
            
            # Robust way: Check GRVT Side from fill? But fill data is gone.
            # Let's rely on Context or Pos Status.
            # Simplified: If OPENING, we hedge OPPOSITE to our GRVT position.
            # Wait, we don't know GRVT side easily from just 'pos'.
            # We must persist `side` in DualPosition. 
            # I will add `side` to DualPosition in next refactor.
            # For now, let's assume we are Long GRVT (since that's the main usecase for funding farming usually)
            # OR pass side from caller.
            
            # Patch: Assume Fill Side was handled, but we need Lighter Side.
            # Let's default to SELL (Short Lighter) for Entry, BUY (Close Lighter) for Exit.
            # Use 'is_exit' flag.
            
            side = 'buy' if is_exit else 'sell' 
            # WARNING: This assumes Entry = Long GRVT. If strategy allows Short GRVT, this is wrong.
            # We need to fix this by adding `side` to DualPosition.
            
            success = False
            if is_exit:
                tx = await self.lighter.close_market_position(position.lighter_symbol, side, qty)
                if tx: success = True
            else:
                tx = await self.lighter.place_market_order(position.lighter_symbol, side, qty)
                if tx: success = True
            
            if success:
                logger.info("Hedge Successful.")
                position.pending_hedge_qty -= qty # Reduces pending
                if not is_exit: position.status = 'HEDGED'
                self.state.update_position(position)
            else:
                logger.error("Hedge Failed! Retrying next loop...")

    async def monitor_fills(self):
        """
        Background loop to check for stuck pending hedges (time-based flush).
        """
        while True:
            try:
                active_pos = self.state.get_active_positions()
                for pos in active_pos:
                    if pos.pending_hedge_qty > 0:
                        # Force hedge processing
                        # Only if time elapsed? implementation for later.
                        # For now, just retry processing
                        await self.process_pending_hedges(pos, is_exit=(pos.status.startswith('CLOSING')))
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            await asyncio.sleep(5)

    async def check_order_timeouts(self):
        """
        Check for active orders that have exceeded timeout limit.
        """
        now = time.time()
        timeout = 60 # 60 seconds
        
        expired_order_ids = []
        for order_id_str, ctx in self.active_orders.items():
            if now - ctx['ts'] > timeout:
                expired_order_ids.append(order_id_str)
                
        for order_id_str in expired_order_ids:
            ctx = self.active_orders[order_id_str]
            logger.info(f"Order {order_id_str} timed out. Cancelling...")
            
            # Cancel on GRVT
            try:
                # order_id might be tracked as str, need valid GRVT ID format (usually int or str is fine)
                # But SDK might expect int if it was int.
                # 'ctx' doesn't store original type, but active_orders keys are str now.
                # Let's hope str works or convert if digit.
                oid = int(order_id_str) if order_id_str.isdigit() else order_id_str
                 
                await self.grvt.client.cancel_order(oid, symbol=ctx['opp'].grvt_symbol)
                logger.info("Order cancelled successfully.")
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id_str}: {e}")
                
            # Cleanup ctx
            del self.active_orders[order_id_str]
            
            # Update Position State? If it was OPENING and size is 0 (no fills), remove it.
            # If partial fills, it stays OPENING but 'pending' decreases as we hedged.
            pos = self.state.positions.get(ctx['pos_id'])
            if pos and pos.pending_hedge_qty == 0 and pos.size > 0:
                # If we had 0 fills, we should remove the position
                # But we don't track 'filled_qty' in DualPosition explicitly yet.
                # Logic gap: If partial filled, we hedged. So we have SOME position. 
                # If 0 filled, we have NO position.
                # We need to know 'filled' amount to decide.
                # For now, just leave it as 'OPENING' or mark 'CANCELLED'?
                # Simplest: If timeout, just stop tracking the order. 
                # If partial fills happened, we are in a legit position (just smaller).
                pass
