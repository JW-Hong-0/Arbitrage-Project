import asyncio
import logging
import os
import sys
import signal

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Environments
os.environ["GRVT_ENV"] = "PROD"
os.environ["LIGHTER_ENV"] = "MAINNET"

from src.GRVT_Lighter_Bot.exchanges.grvt_api import GrvtExchange
from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange
from src.GRVT_Lighter_Bot.strategy.bot_state import BotState
from src.GRVT_Lighter_Bot.strategy.opportunity_scanner import OpportunityScanner
from src.GRVT_Lighter_Bot.strategy.position_manager import PositionManager
from src.GRVT_Lighter_Bot.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "Main_bot_log.txt"), mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("MainBot")

from src.GRVT_Lighter_Bot.dashboard import Dashboard

class ArbitrageBot:
    def __init__(self):
        self.running = True
        self.grvt = GrvtExchange()
        self.lighter = LighterExchange()
        self.state = BotState()
        self.scanner = OpportunityScanner(self.grvt, self.lighter)
        self.pm = PositionManager(self.grvt, self.lighter, self.state)
        self.dashboard = Dashboard(self)
        
    async def initialize(self):
        logger.info("Initializing Exchanges...")
        await self.grvt.initialize()
        await self.lighter.initialize()
        logger.info("Exchanges Initialized.")
        
        # Start Lighter WS (Background)
        asyncio.create_task(self.lighter.start_ws())

    async def ws_fill_callback(self, msg):
        """
        Routes GRVT WS messages to PositionManager.
        """
        # GRVT Fill: { 'instrument': ..., 'price': ..., 'size': ..., 'side': ..., 'order_id': ... }
        if isinstance(msg, dict):
            if ('order_id' in msg and 'price' in msg) or (msg.get('type') == 'fill'):
                 # Normalize if needed
                 data = msg['data'] if msg.get('type') == 'fill' else msg
                 await self.pm.handle_grvt_fill(data)

    async def run(self):
        await self.initialize()
        
        # Start GRVT WS
        logger.info("Starting GRVT WebSocket...")
        ws_task = asyncio.create_task(self.grvt.listen_fills(self.ws_fill_callback))
        
        # Start Position Monitor (Partial Fills & Rotation & Timeouts)
        monitor_task = asyncio.create_task(self.pm.monitor_fills())
        timeout_task = asyncio.create_task(self._monitor_timeouts())
        logger.info("Position & Timeout Monitors Started.")
        
        logger.info("Bot Started. Entering Main Loop (LIVE MODE)...")
        try:
            while self.running:
                # 1. Active Position Status Log
                active_pos = self.state.get_active_positions()
                if active_pos:
                    logger.info(f"Active Positions: {len(active_pos)}")
                    # TODO: Check Rotation/Exit Logic Here
                
                # 2. Opportunity Scan
                # Check Config Limit
                limit = getattr(Config, 'MAX_ACTIVE_POSITIONS', 5)
                
                # Always scan to update dashboard
                opps = await self.scanner.scan()
                await self.dashboard.print_dashboard()
                
                if len(active_pos) < limit and opps:
                        best_opp = opps[0]
                        logger.info(f"Opportunity Found: {best_opp.symbol} Spread: {best_opp.spread:.6f} Dir: {best_opp.direction}")
                        
                        # Calculate Entry Size
                        base_size = 0.0
                        
                        # 1. Try Config-based USDT sizing
                        target_usdt = getattr(Config, 'PER_TRADE_AMOUNT_USDT', 20.0)
                        
                        if best_opp.grvt_price > 0:
                            raw_size = target_usdt / best_opp.grvt_price
                            base_size = raw_size
                        else:
                            # Fallback if price missing (rare now)
                            if best_opp.grvt_symbol in self.grvt.market_rules:
                                min_size = float(self.grvt.market_rules[best_opp.grvt_symbol].get('min_size') or 0)
                                base_size = min_size * 2
                            
                            # Hardcode minimal safe size for fallback
                            if base_size == 0:
                                if 'XRP' in best_opp.symbol: base_size = 20.0
                                elif 'ETH' in best_opp.symbol: base_size = 0.02
                                
                        logger.info(f"Calculated Entry Size: {base_size} (Price: {best_opp.grvt_price}, Target Used: ${target_usdt})")
                        
                        # Execute Entry (LIVE)
                        # Ensure size is enough
                        if base_size > 0:
                            await self.pm.execute_entry_strategy(best_opp, base_size)
                            logger.info(f"Executed Entry for {best_opp.symbol} size {base_size}")
                        else:
                            logger.error(f"Entry Skipped: Calculated Size is 0 for {best_opp.symbol}")

                await asyncio.sleep(10) # Faster refresh for dashboard (10s)
                
        except asyncio.CancelledError:
            logger.info("Bot logic cancelled.")
        except Exception as e:
            logger.error(f"Main Loop Error: {e}", exc_info=True)
        finally:
            self.running = False
            await self.grvt.close()
            await self.lighter.close()
            if not ws_task.done(): ws_task.cancel()
            if not monitor_task.done(): monitor_task.cancel()

    async def _monitor_timeouts(self):
        while self.running:
            await self.pm.check_order_timeouts()
            await asyncio.sleep(10)

def handle_sigint(signum, frame):
    logging.info("Stopping Bot...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    bot = ArbitrageBot()
    asyncio.run(bot.run())
