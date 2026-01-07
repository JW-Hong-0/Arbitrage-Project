import asyncio
import logging
import os
from .config import Config
from .exchanges.grvt_api import GrvtExchange
from .exchanges.lighter_api import LighterExchange

logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self):
        self.grvt = GrvtExchange()
        self.lighter = LighterExchange()
        self.running = False
        self.market_data_loaded = False
        self.processed_trade_ids = set() # To track hedged trades

    async def initialize_markets(self):
        """Load market details from both exchanges."""
        if self.market_data_loaded:
            return
        logger.info("Loading market data for both exchanges...")
        self.market_data_loaded = True
        logger.info("Market data setup complete.")

    async def run(self):
        self.running = True
        logger.info("Strategy starting in MONITOR mode...")

        try:
            await self.grvt.initialize()
            await self.lighter.initialize()
            await self.initialize_markets()
        except Exception as e:
            logger.error(f"Failed to initialize exchanges: {e}")
            self.running = False
            return
        
        logger.info("Strategy started successfully.")
        
        # WEBSOCKET DISABLED to prevent event loop conflict
        # asyncio.create_task(self.grvt.listen_fills(self.on_fill))
        
        while self.running:
            try:
                # 1. Asset Check
                grvt_bal = await self.grvt.get_balance()
                lighter_bal = await self.lighter.get_balance()
                
                # 2. Market Data Fetch
                market_data = await self.get_market_data(Config.SYMBOL)
                
                # 3. Print Dashboard
                self.print_dashboard(market_data, grvt_bal, lighter_bal)

                # 4. Check for new GRVT fills via REST Polling
                await self.poll_for_fills()

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}", exc_info=True)
            
            await asyncio.sleep(10) # Update every 10 seconds

    async def poll_for_fills(self):
        """Periodically check for new trades on GRVT via REST API."""
        try:
            # fetch_my_trades is a standard CCXT method, but needs to be run in a thread
            recent_trades = await asyncio.to_thread(
                self.grvt.client.fetch_my_trades,
                f"{Config.SYMBOL.split('-')[0]}_USDT_Perp",
                None, # Since timestamp
                10 # Limit
            )
            
            if not recent_trades:
                return

            for trade in recent_trades:
                trade_id = trade.get('id')
                if trade_id and trade_id not in self.processed_trade_ids:
                    logger.info(f"Found new GRVT trade via REST Polling: ID {trade_id}")
                    self.processed_trade_ids.add(trade_id)
                    fill_data = {
                        "instrument": trade.get('symbol'),
                        "side": trade.get('side'),
                        "size": trade.get('amount'),
                        "price": trade.get('price'),
                        "id": trade_id
                    }
                    await self.on_fill(fill_data)

        except Exception as e:
            logger.error(f"Error polling for fills: {e}")


    async def get_market_data(self, symbol):
        """
        Fetches detailed market data for a symbol from both exchanges.
        """
        grvt_symbol = f"{symbol.split('-')[0]}_USDT_Perp"
        lighter_symbol = symbol.split('-')[0]

        async def get_grvt_data():
            try:
                # This CCXT-style method needs to be run in a thread
                ticker = await asyncio.to_thread(self.grvt.client.fetch_ticker, grvt_symbol)
                return {
                    "price": ticker.get('last') or 'N/A',
                    "bid": ticker.get('bid') or 'N/A',
                    "ask": ticker.get('ask') or 'N/A',
                    "funding_rate": ticker.get('info', {}).get('funding_rate') or 'N/A',
                    "funding_time": ticker.get('info', {}).get('next_funding_time') or 'N/A',
                    "min_size": "N/A", 
                    "max_leverage": "N/A"
                }
            except Exception as e:
                logger.warning(f"Could not fetch GRVT market data: {e}")
                return None

        async def get_lighter_data():
            try:
                rates_data = await self.lighter.get_all_tickers()
                funding_info = None
                if isinstance(rates_data, list):
                    for r in rates_data:
                        sym = getattr(r, 'symbol', None)
                        if sym and (lighter_symbol in sym):
                            funding_info = { "funding_rate": getattr(r, 'rate_daily', None) }
                            break
                
                return {
                    "price": "N/A", "bid": "N/A", "ask": "N/A",
                    "funding_rate": funding_info.get("funding_rate") if funding_info else "N/A",
                    "funding_time": "N/A", "min_size": "N/A", "max_leverage": "N/A"
                }
            except Exception as e:
                logger.warning(f"Could not fetch Lighter market data: {e}")
                return None

        grvt_data, lighter_data = await asyncio.gather(get_grvt_data(), get_lighter_data())
        
        return { "symbol": symbol, "grvt": grvt_data, "lighter": lighter_data }

    def print_dashboard(self, market_data, grvt_bal, lighter_bal):
        class C:
            HEADER = '\033[95m'; BLUE = '\033[94m'; GREEN = '\033[92m'
            YELLOW = '\033[93m'; RED = '\033[91m'; ENDC = '\033[0m'; BOLD = '\033[1m'

        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{C.BOLD}{C.HEADER}================= GRVT-Lighter Market Monitor ================={C.ENDC}")
        print(f"Bot Mode: {C.YELLOW}MONITORING ONLY (REST Polling for Fills){C.ENDC} | Symbol: {C.BOLD}{Config.SYMBOL}{C.ENDC}")
        
        print(f"\n{C.BOLD}---------- Balances ----------{C.ENDC}")
        print(f"GRVT    | Equity: {C.GREEN}${grvt_bal.get('equity', 0):,.2f}{C.ENDC} | Available: ${grvt_bal.get('available', 0):,.2f}")
        print(f"Lighter | Equity: {C.GREEN}${lighter_bal.get('equity', 0):,.2f}{C.ENDC} | Available: ${lighter_bal.get('available', 0):,.2f}")

        print(f"\n{C.BOLD}---------- Market Data Comparison ({Config.SYMBOL}) ----------{C.ENDC}")
        
        grvt_data = market_data.get('grvt', {}) or {}
        lighter_data = market_data.get('lighter', {}) or {}

        grvt_fr = grvt_data.get('funding_rate', 'N/A')
        lighter_fr = lighter_data.get('funding_rate', 'N/A')

        print(f"{'Metric':<18} | {C.BLUE}{'GRVT':<25}{C.ENDC} | {C.BLUE}{'Lighter':<25}{C.ENDC}")
        print("-" * 70)
        print(f"{'Last Price':<18} | {grvt_data.get('price', 'N/A'):<25} | {lighter_data.get('price', 'N/A'):<25}")
        print(f"{'Best Bid':<18} | {grvt_data.get('bid', 'N/A'):<25} | {lighter_data.get('bid', 'N/A'):<25}")
        print(f"{'Best Ask':<18} | {grvt_data.get('ask', 'N/A'):<25} | {lighter_data.get('ask', 'N/A'):<25}")
        print(f"{C.YELLOW}{'Funding Rate (8h)':<18}{C.ENDC} | {C.YELLOW}{grvt_fr:<25}{C.ENDC} | {C.YELLOW}{lighter_fr:<25}{C.ENDC}")
        print(f"{'Funding Time':<18} | {grvt_data.get('funding_time', 'N/A'):<25} | {lighter_data.get('funding_time', 'N/A'):<25}")
        print(f"{'Min Order Size':<18} | {grvt_data.get('min_size', 'N/A'):<25} | {lighter_data.get('min_size', 'N/A'):<25}")
        print(f"{'Max Leverage':<18} | {grvt_data.get('max_leverage', 'N/A'):<25} | {lighter_data.get('max_leverage', 'N/A'):<25}")

        print("\n" + "="*70)

    async def on_fill(self, fill_data):
        logger.info(f"Fill received: {fill_data}")
        
        try:
            if isinstance(fill_data, str):
                import json
                try: fill_data = json.loads(fill_data)
                except: pass
            
            symbol = Config.SYMBOL 
            side = 'buy'
            amount = Config.ORDER_AMOUNT
            
            if isinstance(fill_data, dict):
                symbol = fill_data.get('instrument', symbol).split('_')[0]
                side = fill_data.get('side', side)
                amount = float(fill_data.get('size', fill_data.get('amount', amount)))
            
            hedge_side = 'sell' if side.lower() == 'buy' else 'buy'
            
            logger.info(f"Hedging: {hedge_side.upper()} {amount} {symbol} on Lighter")
            
            # Since this is a monitor, we won't actually place the hedge order
            # await self.lighter.place_market_order(symbol, hedge_side, amount)
            logger.info(f"[MONITOR MODE] Hedge order not placed.")
                 
        except Exception as e:
            logger.error(f"Error during hedge simulation: {e}")

    async def stop(self):
        self.running = False
        logger.info("Closing exchange connections...")
        await self.lighter.close()
        await self.grvt.close()
        logger.info("Connections closed.")
