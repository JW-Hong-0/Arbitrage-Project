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
        
    async def initialize(self):
        """Asynchronous initializer for API consistency."""
        # GRVT's client is initialized synchronously, so this is a placeholder.
        logger.info("GrvtExchange initialized.")
        pass

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

