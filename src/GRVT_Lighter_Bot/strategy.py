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
        self.processed_trade_ids = set()
        self.trading_rules = {}

    async def load_trading_rules(self):
        """
        Runs once at startup to fetch and store trading rules.
        """
        logger.info("Loading trading rules for both exchanges...")
        symbol = Config.SYMBOL
        
        # --- GRVT Rule Loading ---
        grvt_info = await self.grvt.get_ticker_info(symbol)
        if grvt_info:
            self.trading_rules['grvt'] = {
                'min_size': grvt_info.get('min_qty', 'N/A'),
                'max_leverage': grvt_info.get('max_leverage', 'N/A'),
            }
        else:
            self.trading_rules['grvt'] = {'min_size': 'N/A', 'max_leverage': 'N/A'}

        # --- Lighter Rule Loading ---
        lighter_info = await self.lighter.get_ticker_info(symbol)
        if lighter_info:
             self.trading_rules['lighter'] = {
                'min_size': lighter_info.get('min_qty', 'N/A'),
                'max_leverage': lighter_info.get('max_leverage', 'N/A'),
            }
        else:
             self.trading_rules['lighter'] = {'min_size': 'N/A', 'max_leverage': 'N/A'}
             
        logger.info(f"Trading rules loaded: {self.trading_rules}")


    async def run(self):
        self.running = True
        logger.info("Strategy starting in MONITOR mode...")

        try:
            # Initialize exchanges, which now also loads market rules for GRVT
            await self.grvt.initialize()
            await self.lighter.initialize()
            # Load trading rules for the specific symbol
            await self.load_trading_rules()
        except Exception as e:
            logger.error(f"Failed to initialize exchanges or rules: {e}")
            self.running = False
            return
        
        logger.info("Strategy started successfully.")
        
        while self.running:
            try:
                grvt_bal = await self.grvt.get_balance()
                lighter_bal = await self.lighter.get_balance()
                market_data = await self.get_market_data(Config.SYMBOL)
                self.print_dashboard(market_data, grvt_bal, lighter_bal)
                await self.poll_for_fills()
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
        # Using self.grvt.get_funding_info and existing client methods
        
        # 1. GRVT
        async def get_grvt_data():
            try:
                # Use gather to fetch ticker and funding if needed, or rely on fetch_ticker
                # CCXT fetch_ticker sometimes includes funding, but let's be explicit
                ticker_task = asyncio.to_thread(self.grvt.client.fetch_ticker, Utils.to_grvt_symbol(symbol))
                funding_task = self.grvt.get_funding_info(symbol)
                
                ticker, funding = await asyncio.gather(ticker_task, funding_task)
                
                return {
                    "price": ticker.get('last_price') or 'N/A',
                    "bid": ticker.get('best_bid_price') or 'N/A',
                    "ask": ticker.get('best_ask_price') or 'N/A',
                    "funding_rate": funding.get('funding_rate') if funding.get('funding_rate') is not None else (ticker.get('funding_rate') or 'N/A'),
                    "funding_time": funding.get('next_funding_time') if funding.get('next_funding_time') is not None else 'N/A',
                }
            except Exception as e:
                logger.warning(f"Could not fetch GRVT market data: {e}")
                return None

    async def get_market_data(self, symbol):
        base_symbol = symbol.split('-')[0]
        
        # 1. GRVT
        async def get_grvt_data():
            try:
                # Use gather to fetch ticker and funding if needed, or rely on fetch_ticker
                # CCXT fetch_ticker sometimes includes funding, but let's be explicit
                ticker_task = asyncio.to_thread(self.grvt.client.fetch_ticker, Utils.to_grvt_symbol(symbol))
                funding_task = self.grvt.get_funding_info(symbol)
                
                ticker, funding = await asyncio.gather(ticker_task, funding_task)
                
                return {
                    "price": ticker.get('last_price') or 'N/A',
                    "bid": ticker.get('best_bid_price') or 'N/A',
                    "ask": ticker.get('best_ask_price') or 'N/A',
                    "funding_rate": funding.get('funding_rate') if funding.get('funding_rate') is not None else (ticker.get('funding_rate') or 'N/A'),
                    "funding_time": funding.get('next_funding_time') if funding.get('next_funding_time') is not None else 'N/A',
                }
            except Exception as e:
                logger.warning(f"Could not fetch GRVT market data: {e}")
                return None

        # 2. Lighter
        async def get_lighter_data():
            try:
                # Try new market stats first
                stats = await self.lighter.get_market_stats(symbol)
                
                if stats:
                    return {
                        "price": stats.get('price', 'N/A'),
                        "bid": 'N/A', # Stats might not have bid/ask
                        "ask": 'N/A',
                        "funding_rate": stats.get('funding_rate', 'N/A'),
                        "funding_time": stats.get('next_funding_time', 'N/A')
                    }
                
                # Fallback to direct OrderBook if Stats failed
                logger.warning("Lighter Market Stats failed, falling back to OrderBook...")
                s_base = SYMBOL_ALIASES.get(base_symbol, base_symbol)
                mid = LIGHTER_MARKET_IDS.get(s_base)
                
                ob_url = f"https://testnet.zklighter.elliot.ai/api/v1/orderbook?market_id={mid}"
                if Config.LIGHTER_ENV == "MAINNET":
                     ob_url = f"https://api.lighter.xyz/api/v1/orderbook?market_id={mid}"

                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(ob_url) as resp:
                        ob = await resp.json() if resp.status == 200 else {}

                funding = await self.lighter.get_funding_info(symbol)
                
                ask = str(ob['asks'][0]['price']) if ob.get('asks') else 'N/A'
                bid = str(ob['bids'][0]['price']) if ob.get('bids') else 'N/A'
                price = ask # approx
                
                return {
                    "price": price,
                    "bid": bid,
                    "ask": ask,
                    "funding_rate": funding.get('funding_rate', 'N/A'),
                    "funding_time": funding.get('next_funding_time', 'N/A')
                }
            except Exception as e:
                logger.warning(f"Could not fetch Lighter market data: {e}")
                return {}

        grvt_data, lighter_data = await asyncio.gather(get_grvt_data(), get_lighter_data())
        return {"symbol": symbol, "grvt": grvt_data, "lighter": lighter_data}

    def print_dashboard(self, market_data, grvt_bal, lighter_bal):
        os.system('cls' if os.name == 'nt' else 'clear')
        C = type('C', (), {'HEADER': '\033[95m', 'BLUE': '\033[94m', 'GREEN': '\033[92m', 'YELLOW': '\033[93m', 'RED': '\033[91m', 'ENDC': '\033[0m', 'BOLD': '\033[1m'})
        
        print(f"{C.BOLD}{C.HEADER}================= GRVT-Lighter Market Monitor ================={C.ENDC}")
        print(f"Bot Mode: {C.YELLOW}MONITORING ONLY{C.ENDC} | Symbol: {C.BOLD}{Config.SYMBOL}{C.ENDC}")
        
        print(f"\n{C.BOLD}---------- Balances ----------{C.ENDC}")
        print(f"GRVT    | Equity: {C.GREEN}${grvt_bal.get('equity', 0):,.2f}{C.ENDC} | Available: ${grvt_bal.get('available', 0):,.2f}")
        print(f"Lighter | Equity: {C.GREEN}${lighter_bal.get('equity', 0):,.2f}{C.ENDC} | Available: ${lighter_bal.get('available', 0):,.2f}")

        print(f"\n{C.BOLD}---------- Market Data Comparison ({Config.SYMBOL}) ----------{C.ENDC}")
        
        grvt_data = market_data.get('grvt') or {}
        lighter_data = market_data.get('lighter') or {}
        grvt_rules = self.trading_rules.get('grvt', {})
        lighter_rules = self.trading_rules.get('lighter', {})

        def get(data, key, default='N/A'): return data.get(key, default) or default

        print(f"{'Metric':<18} | {C.BLUE}{'GRVT':<25}{C.ENDC} | {C.BLUE}{'Lighter':<25}{C.ENDC}")
        print("-" * 70)
        print(f"{'Last Price':<18} | {get(grvt_data, 'price'):<25} | {get(lighter_data, 'price'):<25}")
        print(f"{'Best Bid':<18} | {get(grvt_data, 'bid'):<25} | {get(lighter_data, 'bid'):<25}")
        print(f"{'Best Ask':<18} | {get(grvt_data, 'ask'):<25} | {get(lighter_data, 'ask'):<25}")
        print(f"{C.YELLOW}{'Funding Rate (8h)':<18}{C.ENDC} | {C.YELLOW}{get(grvt_data, 'funding_rate'):<25}{C.ENDC} | {C.YELLOW}{get(lighter_data, 'funding_rate'):<25}{C.ENDC}")
        print(f"{'Funding Time':<18} | {get(grvt_data, 'funding_time', 'N/A'):<25} | {get(lighter_data, 'funding_time', 'N/A'):<25}")
        print(f"{'Min Order Size':<18} | {get(grvt_rules, 'min_size'):<25} | {get(lighter_rules, 'min_size'):<25}")
        print(f"{'Max Leverage':<18} | {get(grvt_rules, 'max_leverage'):<25} | {get(lighter_rules, 'max_leverage'):<25}")

        print("\n" + "="*70)

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

