import logging
import asyncio
from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv
from ..config import Config
from ..utils import Utils

logger = logging.getLogger(__name__)

class GrvtExchange:
    def __init__(self):
        env = GrvtEnv.TESTNET if Config.GRVT_ENV == "TESTNET" else GrvtEnv.PROD
        
        # Reference Logic: Get loop and use it for GrvtCcxtWS
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Reference Logic: Suppress Pysdk Logger
        quiet = logging.getLogger("quiet_grvt")
        quiet.setLevel(logging.CRITICAL)
        
        self.client = GrvtCcxt(
            env=env,
            logger=quiet, # Use quiet logger
            parameters={
                "api_key": Config.GRVT_API_KEY,
                "private_key": Config.GRVT_PRIVATE_KEY,
                "trading_account_id": Config.GRVT_TRADING_ACCOUNT_ID,
            }
        )
        self._ws_running = False
        self.market_rules = {}
        self.load_market_rules() # Load rules immediately after client is created
        
    async def initialize(self):
        """Asynchronous initializer for API consistency."""
        # Synchronous client is fully initialized in __init__
        logger.info("GrvtExchange initialized.")
        pass

    def load_market_rules(self):
        """Loads market trading rules by reading the .markets attribute."""
        logger.info("[GRVT] Attempting to load market rules...")
        if not self.client:
            logger.error("❌ [GRVT] Aborting load_market_rules: client is not initialized.")
            return

        try:
            # Check if markets are already populated
            if hasattr(self.client, 'markets') and self.client.markets:
                logger.info(f"[GRVT] Found pre-populated client.markets. Count: {len(self.client.markets)}")
                markets_to_parse = self.client.markets
            else:
                # If not, explicitly call load_markets
                logger.warning("[GRVT] client.markets not populated. Attempting explicit load_markets() call.")
                markets_to_parse = self.client.load_markets()
                logger.info(f"[GRVT] Explicit load_markets() response. Count: {len(markets_to_parse) if markets_to_parse else 0}")

            if not markets_to_parse:
                logger.error("❌ [GRVT] No market data found in either .markets attribute or load_markets() call.")
                return

            for symbol, market in markets_to_parse.items():
                base = symbol.split('/')[0]
                self.market_rules[base] = {
                    'min_size': market.get('limits', {}).get('amount', {}).get('min'),
                    'max_leverage': market.get('limits', {}).get('leverage', {}).get('max', 20),
                }
            logger.info(f"✅ [GRVT] {len(self.market_rules)} market rules loaded.")
            logger.info(f"[GRVT] Loaded rule keys: {list(self.market_rules.keys())}")
        except Exception as e:
            logger.error(f"❌ [GRVT] Failed to parse market rules: {e}", exc_info=True)

    async def get_funding_rate(self, symbol: str):
        """
        Fetch funding rate for the symbol.
        Returns the current funding rate.
        """
        try:
            ticker = await asyncio.to_thread(self.client.fetch_ticker, symbol)
            
            if ticker:
                # Check for funding_rate_curr (default) or fallbacks
                if 'funding_rate_curr' in ticker:
                    return float(ticker['funding_rate_curr'])
                elif 'funding_rate_8h_curr' in ticker:
                     return float(ticker['funding_rate_8h_curr'])
                elif 'funding_rate' in ticker:
                     return float(ticker['funding_rate'])
            return None
        except Exception as e:
            logger.error(f"Error fetching GRVT funding rate: {e}")
            return None

    async def get_all_tickers(self):
        """
        Fetch all tickers to find best funding.
        """
        try:
            tickers = await asyncio.to_thread(self.client.fetch_tickers)
            return tickers
        except Exception as e:
            logger.error(f"Error fetching all GRVT tickers: {e}")
            return {}

    async def place_limit_order(self, symbol: str, side: str, price: float, amount: float):
        try:
            # Quantize amount
            tick_size = 0.0001
            quantized_amount = Utils.quantize_amount(amount, tick_size)
            
            if quantized_amount <= 0:
                logger.error(f"Order amount too small after quantization: {amount} -> {quantized_amount}")
                return None

            # Added post_only to params
            params = {'post_only': True}
            
            order = await asyncio.to_thread(
                self.client.create_order,
                symbol,
                'limit',
                side,
                quantized_amount,
                price,
                params
            )
            logger.info(f"GRVT Order Placed: {order}")
            return order
        except Exception as e:
            logger.error(f"GRVT Order Failed: {e}")
            return None
        
    async def get_balance(self):
        """
        Fetch USDT balance and positions.
        Returns dict with 'equity', 'available', 'positions'.
        """
        try:
            # Run blocking calls in thread
            bal = await asyncio.to_thread(self.client.fetch_balance)
            positions = await asyncio.to_thread(self.client.fetch_positions)
            
            # Parse Balance
            equity = float(bal.get('USDT', {}).get('total', 0))
            available = float(bal.get('USDT', {}).get('free', 0))
            
            # Parse Positions
            active_positions = []
            for p in positions:
                size = float(p.get('size') or p.get('contracts') or 0)
                if size != 0:
                    active_positions.append({
                        'symbol': p.get('symbol'),
                        'size': size,
                        'side': 'long' if size > 0 else 'short',
                        'entry_price': float(p.get('entry_price', 0))
                    })
            
            return {
                'equity': equity,
                'available': available,
                'positions': active_positions
            }
        except Exception as e:
            logger.error(f"Error fetching GRVT balance: {e}")
            # Return safe default
            return {'equity': 0, 'available': 0, 'positions': []}

    async def listen_fills(self, callback):
        """
        Listen for user fills via WebSocket.
        """
        if self._ws_running: return
        self._ws_running = True
        
        while self._ws_running:
            try:
                from pysdk.grvt_ccxt_ws import GrvtCcxtWS
                # Reference Logic: Loop Injection for WS
                loop = asyncio.get_running_loop()
                env = GrvtEnv.TESTNET if Config.GRVT_ENV == "TESTNET" else GrvtEnv.PROD
                
                quiet = logging.getLogger("quiet_grvt_ws")
                quiet.setLevel(logging.CRITICAL)
                
                params = {
                    "api_key": Config.GRVT_API_KEY,
                    "private_key": Config.GRVT_PRIVATE_KEY,
                    "trading_account_id": Config.GRVT_TRADING_ACCOUNT_ID,
                }
                
                self.ws = GrvtCcxtWS(
                    env=env, 
                    loop=loop, 
                    logger=quiet, 
                    parameters=params
                )
                
                await self.ws.initialize()
                logger.info("GRVT WebSocket Initialized.")
                
                # Subscribe to user trades/fills
                await self.ws.subscribe(stream='user.trades', callback=callback)
                logger.info("Subscribed to user.trades")
                
                # Mock keepalive to prevent loop exit in this version
                while self._ws_running:
                     await asyncio.sleep(1)
                     
            except Exception as e:
                logger.error(f"GRVT WS Error: {e}")
                await asyncio.sleep(5)


    async def get_ticker_info(self, symbol):
        """
        Retrieves ticker information including leverage and min size.
        Uses fetch_ticker for price/funding, and cached markets for limits.
        """
        try:
            grvt_symbol = Utils.to_grvt_symbol(symbol)
            
            info = {
                "symbol": symbol,
                "grvt_symbol": grvt_symbol,
                "min_qty": None,
                "max_leverage": None,
                "tick_size": None
            }

            # 1. Get Limits from Market Structure (Instrument Info)
            if hasattr(self.client, 'markets') and self.client.markets and grvt_symbol in self.client.markets:
                m = self.client.markets[grvt_symbol]
                info["min_qty"] = m.get('limits', {}).get('amount', {}).get('min')
                # Fallback to key 'min_size' if custom structure
                if info["min_qty"] is None:
                     info["min_qty"] = m.get('min_size')
                
                info["tick_size"] = m.get('precision', {}).get('price') # CCXT standard
                if info["tick_size"] is None:
                     info["tick_size"] = m.get('tick_size')

            # Leverage - fetch from specific endpoint as per user
            try:
                acc_id = self.client.get_trading_account_id()
                payload = {"sub_account_id": acc_id}
                
                # Construct URL
                base_url = "https://trades.grvt.io"
                if "TESTNET" in str(self.client.env):
                    base_url = "https://trades.testnet.grvt.io"
                
                url = f"{base_url}/full/v1/get_all_initial_leverage"
                
                # Use client's internal method for auth post if available
                if hasattr(self.client, '_auth_and_post'):
                    resp = await asyncio.to_thread(self.client._auth_and_post, url, payload=payload)
                    # { "results": [{ "instrument": "...", "leverage": "10", ... }] }
                    results = resp.get('results', [])
                    target = next((r for r in results if r.get('instrument') == grvt_symbol), None)
                    if target:
                        info["max_leverage"] = target.get('max_leverage') # Correct field
            except Exception as e:
                logger.warning(f"Failed to fetch leverage via raw call: {e}")
                
            if info["max_leverage"] is None:
                # Fallback to market info if available
                info["max_leverage"] = m.get('limits', {}).get('leverage', {}).get('max')
                
            return info
        except Exception as e:
            logger.error(f"Error fetching GRVT ticker info for {symbol}: {e}")
            return None

    async def get_funding_info(self, symbol):
        """
        Fetches funding rate and time via REST.
        """
        try:
            grvt_symbol = Utils.to_grvt_symbol(symbol)
            # Fetch Ticker which contains funding info
            ticker = self.client.fetch_ticker(grvt_symbol)
            
            # Map fields based on CCXT standard + GRVT specifics
            # User provided: funding_rate, next_funding_time
            return {
                "funding_rate": ticker.get('fundingRate'), # CCXT normalized
                "next_funding_time": ticker.get('nextFundingDateTime') or ticker.get('next_funding_time'), # CCXT usually provides this
                "mark_price": ticker.get('markPrice') or ticker.get('mark_price')
            }
        except Exception as e:
            # logger.warning(f"Error fetching GRVT funding info: {e}")
            return {"funding_rate": None, "next_funding_time": None}

    async def close(self):
        """Gracefully close the underlying client session."""
        self._ws_running = False
        if hasattr(self, 'ws') and self.ws:
            # Add logic to close ws if the sdk supports it
            pass
        if self.client and hasattr(self.client, '_session') and self.client._session:
            if not self.client._session.closed:
                await self.client._session.close()
                logger.info("GRVT client session closed.")

