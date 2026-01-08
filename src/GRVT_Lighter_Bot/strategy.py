import asyncio
import logging
import os
from .config import Config
from .exchanges.grvt_api import GrvtExchange
from .exchanges.lighter_api import LighterExchange
from .constants import LIGHTER_MARKET_IDS, GRVT_TICKER_MAP, SYMBOL_ALIASES
from .utils import Utils

logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self):
        self.grvt = GrvtExchange()
        self.lighter = LighterExchange()
        self.running = False
        self.symbols_to_monitor = set()
        self.trading_rules = {}

    async def load_trading_rules(self):
        """
        Runs once at startup to fetch and store trading rules for common symbols.
        """
        if not self.symbols_to_monitor:
            logger.warning("No common symbols found to load trading rules for.")
            return

        for symbol_base in self.symbols_to_monitor:
             symbol = f"{symbol_base}-USDT" # Assuming all are USDT pairs for now
             logger.info(f"Loading trading rules for {symbol}...")
             
             # --- GRVT Rule Loading ---
             grvt_info = await self.grvt.get_ticker_info(symbol)
             grvt_rules = {
                 'min_size': grvt_info.get('min_qty', 'N/A') if grvt_info else 'N/A',
                 'max_leverage': grvt_info.get('max_leverage', 'N/A') if grvt_info else 'N/A',
                 'current_leverage': grvt_info.get('current_leverage', 'N/A') if grvt_info else 'N/A',
             }

             # --- Lighter Rule Loading ---
             lighter_info = await self.lighter.get_ticker_info(symbol)
             lighter_rules = {
                 'min_size': lighter_info.get('min_qty', 'N/A') if lighter_info else 'N/A',
                 'max_leverage': lighter_info.get('max_leverage', 'N/A') if lighter_info else 'N/A',
             }
             
             self.trading_rules[symbol] = {'grvt': grvt_rules, 'lighter': lighter_rules}
             
        logger.info(f"Trading rules loaded for {len(self.trading_rules)} symbols.")


    async def run(self):
        self.running = True
        logger.info("Strategy starting in MONITOR mode...")

        try:
            # 1. Initialize exchange clients
            await self.grvt.initialize()
            await self.lighter.initialize()
            
            # 2. Discover common symbols automatically
            grvt_symbols = self.grvt.load_market_rules()
            lighter_symbols = await self.lighter.load_markets()
            
            # Find intersection and then exclude symbols from the config list
            common_symbols = grvt_symbols.intersection(lighter_symbols)
            if hasattr(Config, 'SYMBOL_EXCLUDE'):
                self.symbols_to_monitor = {s for s in common_symbols if s not in Config.SYMBOL_EXCLUDE}
            else:
                self.symbols_to_monitor = common_symbols
            
            logger.info(f"Found {len(self.symbols_to_monitor)} common symbols to monitor: {self.symbols_to_monitor}")

            # 3. Start WebSocket listeners
            asyncio.create_task(self.lighter.start_ws())
            
            # 4. Load trading rules for the common symbols
            await self.load_trading_rules()

        except Exception as e:
            logger.error(f"Failed to initialize exchanges or rules: {e}", exc_info=True)
            self.running = False
            return
        
        logger.info("Strategy started successfully.")
        
        while self.running:
            try:
                # First, fetch all data (this takes time)
                grvt_bal = await self.grvt.get_balance()
                lighter_bal = await self.lighter.get_balance()
                
                dashboard_data = []
                for symbol_base in self.symbols_to_monitor:
                    symbol = f"{symbol_base}-USDT"
                    md = await self.get_market_data(symbol)
                    dashboard_data.append(md)
                
                # Now, clear the screen and print the new data instantly
                os.system('cls' if os.name == 'nt' else 'clear')
                self.print_dashboard(dashboard_data, grvt_bal, lighter_bal)

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}", exc_info=True)
            
            await asyncio.sleep(10)
    async def poll_for_fills(self):
        """Periodically check for new trades on GRVT via REST API using mapped symbols."""
        try:
            base_symbol = Config.SYMBOL.split('-')[0]
            grvt_symbol = GRVT_TICKER_MAP.get(base_symbol)

            if not grvt_symbol:
                return

            response = await asyncio.to_thread(
                self.grvt.client.fetch_my_trades, grvt_symbol, None, 10
            )

            if not isinstance(response, dict) or 'result' not in response:
                return

            for trade in response.get('result', []):
                if isinstance(trade, dict) and trade.get('id') not in self.processed_trade_ids:
                    self.processed_trade_ids.add(trade['id'])
                    logger.info(f"Found new GRVT trade via REST Polling: ID {trade['id']}")
                    await self.on_fill(trade)

        except Exception as e:
            logger.error(f"Error polling for fills: {e}")

    async def get_market_data(self, symbol):
        base_symbol = symbol.split('-')[0]
        
        async def get_grvt_data():
            try:
                ticker_task = asyncio.to_thread(self.grvt.client.fetch_ticker, Utils.to_grvt_symbol(symbol))
                funding_info_task = self.grvt.get_funding_info(symbol)
                ticker, funding_info = await asyncio.gather(ticker_task, funding_info_task)
                
                raw_rate = funding_info.get('funding_rate')
                return {
                    "price": ticker.get('last_price'),
                    "bid": ticker.get('best_bid_price'),
                    "ask": ticker.get('best_ask_price'),
                    "funding_rate": float(raw_rate) if raw_rate is not None else None,
                    "funding_time": Utils.format_funding_time(funding_info.get('next_funding_time')),
                    "funding_interval": funding_info.get('funding_interval')
                }
            except Exception as e:
                logger.warning(f"Could not fetch GRVT market data for {symbol}: {e}")
                return None

        async def get_lighter_data():
            try:
                stats = await self.lighter.get_market_stats(symbol)
                if stats:
                    stats["funding_time"] = Utils.format_funding_time(stats.get('next_funding_time'))
                return stats
            except Exception as e:
                logger.warning(f"Could not fetch Lighter market data for {symbol}: {e}")
                return {}

        grvt_data, lighter_data = await asyncio.gather(get_grvt_data(), get_lighter_data())

        # Normalize funding rates and calculate difference
        funding_diff = None
        try:
            grvt_rate = float(grvt_data.get('funding_rate', 0))
            lighter_rate = float(lighter_data.get('funding_rate', 0))
            grvt_interval = int(grvt_data.get('funding_interval', 1)) # Default to 1 to avoid ZeroDivisionError
            
            # Lighter is always 1-hour, so normalize it to GRVT's interval
            normalized_lighter_rate = lighter_rate * grvt_interval
            funding_diff = grvt_rate - normalized_lighter_rate
        except (ValueError, TypeError):
            pass # Handles cases where rates are None or N/A

        return {"symbol": symbol, "grvt": grvt_data, "lighter": lighter_data, "funding_diff": funding_diff}

    def print_dashboard(self, dashboard_data_list, grvt_bal, lighter_bal):
        C = type('C', (), {'HEADER': '\033[95m', 'BLUE': '\033[94m', 'GREEN': '\033[92m', 'YELLOW': '\033[93m', 'RED': '\033[91m', 'ENDC': '\033[0m', 'BOLD': '\033[1m'})
        
        def color_rate(rate):
            if rate is None: return f"{'N/A':>8}"
            color = C.GREEN if rate > 0 else C.RED if rate < 0 else C.ENDC
            return f"{color}{rate: >8.5f}{C.ENDC}"

        print(f"{C.BOLD}{C.HEADER}================= GRVT-Lighter Funding Rate Monitor ================={C.ENDC}")
        print(f"Bot Mode: {C.YELLOW}MONITORING ONLY{C.ENDC}")
        print(f"\n{C.BOLD}---------- Balances ----------{C.ENDC}")
        print(f"GRVT    | Equity: {C.GREEN}${grvt_bal.get('equity', 0):,.2f}{C.ENDC} | Available: ${grvt_bal.get('available', 0):,.2f}")
        print(f"Lighter | Equity: {C.GREEN}${lighter_bal.get('equity', 0):,.2f}{C.ENDC} | Available: ${lighter_bal.get('available', 0):,.2f}")
        print("\n" + "="*78)

        # Header
        header = (f"{'Symbol':<7} | {'GRVT Rate':>14} | {'Lighter Rate (Adj)':>20} | {'Diff (GRVT-Ltr)':>17} | {'Recommendation'}")
        print(C.BOLD + header + C.ENDC)
        print("-" * 78)

        # Data Rows
        best_opportunity = {"symbol": None, "diff": 0, "grvt_rate": 0, "lighter_rate": 0}

        for data in dashboard_data_list:
            symbol_base = data.get('symbol', 'N/A').split('-')[0]
            grvt_data = data.get('grvt', {})
            lighter_data = data.get('lighter', {})
            
            grvt_rate = grvt_data.get('funding_rate')
            lighter_rate = lighter_data.get('funding_rate')
            grvt_interval = grvt_data.get('funding_interval', 1)

            # Normalize Lighter rate for comparison
            try:
                norm_lighter_rate = float(lighter_rate) * int(grvt_interval)
            except (ValueError, TypeError):
                norm_lighter_rate = None
            
            funding_diff = data.get('funding_diff')

            # Track best opportunity
            if funding_diff is not None and abs(funding_diff) > abs(best_opportunity['diff']):
                best_opportunity['symbol'] = symbol_base
                best_opportunity['diff'] = funding_diff
                best_opportunity['grvt_rate'] = grvt_rate
                best_opportunity['lighter_rate'] = lighter_rate


            grvt_rate_str = f"{color_rate(grvt_rate)} ({grvt_interval}h)"
            lighter_rate_str = f"{color_rate(lighter_rate)} (1h -> {color_rate(norm_lighter_rate)})"
            diff_str = color_rate(funding_diff)

            recommendation = "N/A"
            if funding_diff is not None:
                if funding_diff > 0: # GRVT > Lighter, so Short GRVT, Long Lighter
                    recommendation = f"{C.RED}Short GRVT{C.ENDC}/{C.GREEN}Long Lighter{C.ENDC}"
                else: # Lighter > GRVT, so Long GRVT, Short Lighter
                    recommendation = f"{C.GREEN}Long GRVT{C.ENDC}/{C.RED}Short Lighter{C.ENDC}"

            row = (f"{symbol_base:<7} | {grvt_rate_str:<14} | {lighter_rate_str:<20} | {diff_str:>17} | {recommendation}")
            print(row)
        
        print("="*78)

        # Print Best Opportunity
        if best_opportunity['symbol']:
            sym = best_opportunity['symbol']
            diff = best_opportunity['diff']
            
            if diff > 0:
                strat_rec = f"{C.RED}Short GRVT{C.ENDC} / {C.GREEN}Long Lighter{C.ENDC}"
            else:
                strat_rec = f"{C.GREEN}Long GRVT{C.ENDC} / {C.RED}Short Lighter{C.ENDC}"

            print(f"\n{C.BOLD}{C.YELLOW}Optimal Strategy Suggestion:{C.ENDC}")
            print(f"  - Symbol: {C.BOLD}{sym}{C.ENDC}")
            print(f"  - Max Funding Diff: {color_rate(diff)}")
            print(f"  - Recommendation: {strat_rec}")
        print("="*78)

    async def on_fill(self, fill_data):
        logger.info(f"Fill received: {fill_data}")
        # Hedging logic is disabled in monitor mode.
        logger.info(f"[MONITOR MODE] Hedge order not placed.")

    async def stop(self):
        self.running = False
        logger.info("Closing exchange connections...")
        await self.lighter.close()
        await self.grvt.close()
        logger.info("Connections closed.")

