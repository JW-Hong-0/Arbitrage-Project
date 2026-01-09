import asyncio
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..exchanges.grvt_api import GrvtExchange
from ..exchanges.lighter_api import LighterExchange
from ..config import Config

logger = logging.getLogger(__name__)

@dataclass
class arbitrage_opportunity:
    symbol: str          # Base symbol e.g., "ETH"
    grvt_symbol: str
    lighter_symbol: str
    grvt_funding_rate: float
    lighter_funding_rate: float
    spread: float        
    estimated_annual_apy: float
    timestamp: float
    direction: str = 'Long_GRVT' # 'Long_GRVT' or 'Short_GRVT'
    grvt_funding_interval_hours: int = 8 # Default 8h
    lighter_funding_interval_hours: int = 1 # Default 1h
    adj_grvt_rate_1h: float = 0.0
    adj_lighter_rate_1h: float = 0.0
    grvt_price: float = 0.0
    lighter_price: float = 0.0

class OpportunityScanner:
    def __init__(self, grvt: GrvtExchange, lighter: LighterExchange):
        self.grvt = grvt
        self.lighter = lighter
        self.opportunities: Dict[str, arbitrage_opportunity] = {}
        self.min_spread = Config.FUNDING_DIFF_THRESHOLD or 0.0001 

    async def scan(self) -> List[arbitrage_opportunity]:
        """
        Scans both exchanges for funding rate discrepancies.
        """
        if not self.lighter.market_rules:
            await self.lighter.load_markets()
            
        common_symbols = self._get_common_symbols()
        logger.debug(f"Scanning {len(common_symbols)} common symbols.")
        
        # Optimize: Fetch ALL GRVT tickers at once to avoid n * request latency
        try:
            grvt_tickers = await asyncio.to_thread(self.grvt.client.fetch_tickers)
        except Exception:
            grvt_tickers = {}

        results = []
        missing_symbols = []
        
        # 1. Fast Path: Process symbols found in batch
        for symbol in common_symbols:
            grvt_sym = f"{symbol}_USDT_Perp"
            grvt_ticker = grvt_tickers.get(grvt_sym)
            
            # Fallback checks
            if not grvt_ticker: grvt_ticker = grvt_tickers.get(f"{symbol}-USDT")
            if not grvt_ticker:
                 for k, v in grvt_tickers.items():
                    if k.startswith(symbol + "_") or k.startswith(symbol + "/") or k.startswith(symbol + "-"):
                        grvt_ticker = v
                        break
            
            if grvt_ticker:
                opp = await self._process_single_symbol(symbol, grvt_ticker)
                if opp: results.append(opp)
            else:
                missing_symbols.append(symbol)

        # 2. Slow Path: Parallel Fetch for missing symbols
        if missing_symbols:
            logger.info(f"Parallel fetching {len(missing_symbols)} missing symbols...")
            chunk_size = 10
            for i in range(0, len(missing_symbols), chunk_size):
                chunk = missing_symbols[i:i+chunk_size]
                chunk_tasks = []
                for sym in chunk:
                    chunk_tasks.append(self._fetch_and_process_individual_grvt(sym))
                
                chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
                for res in chunk_results:
                    if isinstance(res, arbitrage_opportunity):
                        results.append(res)
                await asyncio.sleep(0.5) 

        results.sort(key=lambda x: x.spread, reverse=True)
        self.opportunities = {op.symbol: op for op in results}
        return results

    async def _process_single_symbol(self, symbol, grvt_ticker):
        try:
             grvt_price = float(
                grvt_ticker.get('mark_price') or 
                grvt_ticker.get('index_price') or 
                grvt_ticker.get('last') or 
                grvt_ticker.get('close') or 
                0.0
             )
             grvt_fr = float(grvt_ticker.get('funding_rate') or 0.0)
             
             l_stats = await self.lighter.get_market_stats(symbol)
             lighter_fr = float(l_stats.get('funding_rate') or 0.0)
             lighter_price = float(l_stats.get('price') or l_stats.get('index_price') or l_stats.get('mark_price') or 0.0)

             return self._create_opp_object(symbol, grvt_ticker.get('symbol', symbol), grvt_fr, grvt_price, lighter_fr, lighter_price)
        except Exception:
             return None

    async def _fetch_and_process_individual_grvt(self, symbol):
        try:
            grvt_sym = f"{symbol}_USDT_Perp"
            grvt_ticker = await asyncio.to_thread(self.grvt.client.fetch_ticker, grvt_sym)
            if not grvt_ticker: return None
            return await self._process_single_symbol(symbol, grvt_ticker)
        except Exception:
            return None

    def _create_opp_object(self, symbol, grvt_sym, grvt_fr, grvt_price, lighter_fr, lighter_price):
             # 3. Calculate Spread
             spread_A = -grvt_fr + lighter_fr
             spread_B = grvt_fr - lighter_fr
             
             best_spread = 0.0
             direction = None 
             
             if spread_A > spread_B:
                 best_spread = spread_A
                 direction = 'Long_GRVT' 
             else:
                 best_spread = spread_B
                 direction = 'Short_GRVT'
            
             grvt_interval = 8 
             lighter_interval = 1
             
             adj_grvt = grvt_fr / grvt_interval
             
             # User wants: "Expected larger value when converted to GRVT time".
             # So we should show: lighter_fr * grvt_interval
             display_lighter_rate = lighter_fr * grvt_interval 
             
             return arbitrage_opportunity(
                    symbol=symbol,
                    grvt_symbol=grvt_sym,
                    lighter_symbol=symbol,
                    grvt_funding_rate=grvt_fr,
                    lighter_funding_rate=lighter_fr,
                    spread=best_spread,
                    estimated_annual_apy=best_spread * 3 * 365,
                    timestamp=time.time(),
                    direction=direction,
                    grvt_funding_interval_hours=grvt_interval,
                    lighter_funding_interval_hours=lighter_interval,
                    adj_grvt_rate_1h=adj_grvt, 
                    adj_lighter_rate_1h=display_lighter_rate, 
                    grvt_price=grvt_price,
                    lighter_price=lighter_price
                )

    def _get_common_symbols(self) -> List[str]:
        g_syms = set()
        for k in self.grvt.market_rules.keys():
            base = k.split('_')[0].split('-')[0]
            g_syms.add(base)
            
        l_syms = set()
        for k in self.lighter.market_rules.keys():
             l_syms.add(k.split('-')[0]) # Ensure base symbol mapping for Lighter too
        
        common = list(g_syms.intersection(l_syms))
        logger.info(f"Common Symbols Found ({len(common)}): {common[:10]}...")
        if not common:
            logger.warning(f"No common symbols found! GRVT Keys: {list(g_syms)[:5]}..., Lighter Keys: {list(l_syms)[:5]}...")
            
        return common
