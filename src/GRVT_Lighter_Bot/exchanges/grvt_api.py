import logging
import asyncio
from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv
from ..config import Config

logger = logging.getLogger(__name__)

class GrvtExchange:
    def __init__(self):
        env = GrvtEnv.TESTNET if Config.GRVT_ENV == "TESTNET" else GrvtEnv.PROD
        self.client = GrvtCcxt(
            env=env,
            logger=logger,
            parameters={
                "api_key": Config.GRVT_API_KEY,
                "private_key": Config.GRVT_PRIVATE_KEY,
                "sub_account_id": Config.GRVT_TRADING_ACCOUNT_ID,
            }
        )
        
    async def get_funding_rate(self, symbol: str):
        """
        Fetch funding rate for the symbol.
        Returns the current funding rate.
        Note: The unit needs verification (likely raw 1e9 or similar).
        """
        try:
            # fetch_ticker is synchronous in the SDK based on the class definition I saw?
            # The class GrvtCcxt inherited from GrvtCcxtBase and uses requests.
            # So this is blocking. I should run in executor if I need async.
            # Or use GrvtRawAsync if available.
            # For now, wrap in to_thread.
            ticker = await asyncio.to_thread(self.client.fetch_ticker, symbol)
            
            if ticker and 'funding_rate_curr' in ticker:
                # Assuming raw value, returning as float
                # Based on legacy code/docs, might need scaling, but raw is safest for diff check
                return float(ticker['funding_rate_curr'])
            return None
        except Exception as e:
            logger.error(f"Error fetching GRVT funding rate: {e}")
            return None

    async def get_all_tickers(self):
        """
        Fetch all tickers to find best funding.
        """
        try:
            # GrvtCcxt has fetch_tickers (plural) usually or we scan known symbols
            # If not available, we might need to fetch instruments first
            # Checking legacy or standard ccxt, usually fetch_tickers
            # For now, let's try fetch_tickers if available, else iterate
            
            # Note: client is synchronous
            tickers = await asyncio.to_thread(self.client.fetch_tickers)
            return tickers
        except Exception as e:
            logger.error(f"Error fetching all GRVT tickers: {e}")
            return {}

    async def place_limit_order(self, symbol: str, side: str, price: float, amount: float):
        try:
            # side: 'buy' or 'sell'
            # price: float
            # amount: float
            order = await asyncio.to_thread(
                self.client.create_order,
                symbol,
                'limit',
                side,
                amount,
                price
            )
            logger.info(f"GRVT Order Placed: {order}")
            return order
        except Exception as e:
            logger.error(f"GRVT Order Failed: {e}")
            return None
        
    async def listen_fills(self, callback):
        """
        Listen to user trades/fills using GrvtCcxtWS and call callback(fill_data).
        """
        try:
            from pysdk.grvt_ccxt_ws import GrvtCcxtWS
            
            # Using the same config as REST client
            # GrvtCcxtWS might need specific initialization
            # Assuming it takes similar params
            # We need to run this in a way that keeps the connection open
            
            self.ws_client = GrvtCcxtWS(
                env=GrvtEnv.TESTNET if Config.GRVT_ENV == "TESTNET" else GrvtEnv.PROD,
                logger=logger,
                parameters={
                    "api_key": Config.GRVT_API_KEY,
                    "private_key": Config.GRVT_PRIVATE_KEY,
                    "sub_account_id": Config.GRVT_TRADING_ACCOUNT_ID,
                }
            )
            
            logger.info("Starting GRVT WebSocket...")
            
            # The WS client in legacy code had a 'watch_my_trades' or similar pattern
            # Using standard CCXT pattern if possible: watch_my_trades(symbol)
            # We need a loop
            
            await self.ws_client.load_markets()
            symbol = Config.SYMBOL
            
            while True:
                try:
                    # watch_my_trades returns a list of trades
                    trades = await self.ws_client.watch_my_trades(symbol)
                    for trade in trades:
                        # Process trade
                        logger.info(f"GRVT Trade/Fill: {trade}")
                        if callback:
                            await callback(trade)
                except Exception as e:
                    logger.error(f"GRVT WS Error: {e}")
                    await asyncio.sleep(5) # Reconnect delay
                    
        except ImportError:
            logger.error("Could not import GrvtCcxtWS. Check SDK installation.")
        except Exception as e:
             logger.error(f"Critical GRVT WS Failure: {e}")
