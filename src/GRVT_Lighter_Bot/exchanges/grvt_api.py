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

    def load_market_rules(self) -> set:
        """Loads market trading rules and returns a set of available base symbols."""
        logger.info("[GRVT] Attempting to load market rules...")
        available_symbols = set()
        if not self.client:
            logger.error("❌ [GRVT] Aborting load_market_rules: client is not initialized.")
            return available_symbols

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
                return available_symbols

            for symbol, market in markets_to_parse.items():
                base = symbol.split('_')[0]
                available_symbols.add(base)
                self.market_rules[base] = {
                    'min_size': market.get('min_size'), # Corrected based on user-provided API docs
                    'max_leverage': market.get('limits', {}).get('leverage', {}).get('max', 20),
                }
            logger.info(f"✅ [GRVT] {len(self.market_rules)} market rules loaded.")
            logger.info(f"[GRVT] Loaded rule keys: {list(self.market_rules.keys())}")
        except Exception as e:
            logger.error(f"❌ [GRVT] Failed to parse market rules: {e}", exc_info=True)
        
        return available_symbols

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
            grvt_symbol = Utils.to_grvt_symbol(symbol) # Convert symbol to GRVT format
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
                grvt_symbol, # Use GRVT-formatted symbol
                'limit',
                side,
                quantized_amount,
                price,
                params
            )
            logger.info(f"GRVT Order Placed: {order}")
            return order
        except Exception as e:
            logger.error(f"GRVT Order Failed: {e}", exc_info=True)
            return None
        
    async def place_market_order(self, symbol: str, side: str, amount: float):
        """
        Places a market order.
        """
        try:
            grvt_symbol = Utils.to_grvt_symbol(symbol) # Convert symbol to GRVT format
            
            # The SDK's create_order method handles market orders by setting type='market' and price=None
            order = await asyncio.to_thread(
                self.client.create_order,
                grvt_symbol, # Use GRVT-formatted symbol
                'market',
                side,
                amount,
                None  # Price is None for market orders
            )
            logger.debug(f"Raw GRVT create_order response: {order}") # More specific debug log
            if order and order.get('id'):
                logger.info(f"GRVT Market Order Placed: {order}")
                return order
            else:
                logger.error(f"Failed to place GRVT market order. Response: {order}")
        except Exception as e:
            logger.error(f"GRVT Market Order Failed for {symbol}: {e}", exc_info=True)
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
        Retrieves ticker information including min_qty and leverage details.
        """
        try:
            grvt_symbol = Utils.to_grvt_symbol(symbol)
            base_symbol = symbol.split('-')[0]

            # Get min_size from the pre-loaded rules, making a copy to prevent cache modification
            info = self.market_rules.get(base_symbol, {}).copy()
            info['min_qty'] = info.get('min_size')

            # Leverage - fetch from specific endpoint as per user docs
            try:
                acc_id = self.client.get_trading_account_id()
                payload = {"sub_account_id": acc_id}
                
                base_url = "https://trades.grvt.io"
                if "TESTNET" in str(self.client.env):
                    base_url = "https://trades.testnet.grvt.io"
                
                url = f"{base_url}/full/v1/get_all_initial_leverage"
                
                if hasattr(self.client, '_auth_and_post'):
                    resp = await asyncio.to_thread(self.client._auth_and_post, url, payload=payload)
                    results = resp.get('results', [])
                    target = next((r for r in results if r.get('instrument') == grvt_symbol), None)
                    if target:
                        info["max_leverage"] = target.get('max_leverage')
                        info["current_leverage"] = target.get('leverage')
            except Exception as e:
                logger.warning(f"Failed to fetch GRVT leverage via raw call: {e}")
                
            return info
        except Exception as e:
            logger.error(f"Error fetching GRVT ticker info for {symbol}: {e}")
            return None

    async def set_leverage(self, symbol: str, leverage: int):
        """
        Sets the initial leverage for a specific instrument.
        """
        try:
            acc_id = self.client.get_trading_account_id()
            grvt_symbol = Utils.to_grvt_symbol(symbol)
            
            payload = {
                "sub_account_id": acc_id,
                "instrument": grvt_symbol,
                "leverage": str(leverage)
            }
            
            base_url = "https://trades.grvt.io"
            if "TESTNET" in str(self.client.env):
                base_url = "https://trades.testnet.grvt.io"
            
            url = f"{base_url}/full/v1/set_initial_leverage"
            
            if hasattr(self.client, '_auth_and_post'):
                # Run the synchronous post call in a separate thread
                resp = await asyncio.to_thread(self.client._auth_and_post, url, payload=payload)
                
                if resp.get('success'):
                    logger.info(f"✅ Successfully set GRVT leverage for {grvt_symbol} to {leverage}x.")
                    return True
                else:
                    logger.error(f"❌ Failed to set GRVT leverage for {grvt_symbol}. Response: {resp}")
                    return False
            else:
                logger.error("❌ Cannot set GRVT leverage: _auth_and_post method not found on client.")
                return False
        except Exception as e:
            logger.error(f"❌ Error setting GRVT leverage for {symbol}: {e}", exc_info=True)
            return False

    async def get_funding_interval(self, symbol: str) -> int | None:
        """
        Fetches the funding interval in hours using the official SDK method.
        """
        try:
            grvt_symbol = Utils.to_grvt_symbol(symbol)
            # Use the official SDK method to be more robust
            history = await asyncio.to_thread(self.client.fetch_funding_rate_history, grvt_symbol, limit=1)
            results = history.get('result', [])
            if results and 'funding_interval_hours' in results[0]:
                return int(results[0]['funding_interval_hours'])
            return None
        except Exception as e:
            logger.warning(f"Could not fetch funding interval for {symbol}: {e}")
            return None

    async def get_funding_info(self, symbol):
        """
        Fetches funding rate and time via REST, and funding interval.
        """
        try:
            grvt_symbol = Utils.to_grvt_symbol(symbol)
            ticker_task = asyncio.to_thread(self.client.fetch_ticker, grvt_symbol)
            interval_task = self.get_funding_interval(symbol)
            
            ticker, interval = await asyncio.gather(ticker_task, interval_task)
            
            # The user-provided doc shows `next_funding_time` is in the ticker response
            return {
                "funding_rate": ticker.get('funding_rate'),
                "next_funding_time": ticker.get('next_funding_time'),
                "funding_interval": interval
            }
        except Exception as e:
            logger.warning(f"Error fetching GRVT funding info for {symbol}: {e}")
            return {"funding_rate": None, "next_funding_time": None, "funding_interval": None}

    async def close(self):
        """Gracefully close the underlying client session."""
        self._ws_running = False
        if hasattr(self, 'ws') and self.ws:
            # The GrvtCcxtWS class handles its own shutdown
            pass
        if self.client and hasattr(self.client, '_session') and self.client._session:
            # This is a synchronous requests.Session, so no await
            self.client._session.close()
            logger.info("GRVT client session closed.")

