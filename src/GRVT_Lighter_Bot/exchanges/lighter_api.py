import logging
import asyncio
from lighter.api.funding_api import FundingApi
from lighter.api_client import ApiClient
from lighter.configuration import Configuration
from lighter.models.funding_rates import FundingRates
from lighter.signer_client import SignerClient
from ..config import Config
from ..utils import Utils
from ..constants import LIGHTER_MARKET_IDS, SYMBOL_ALIASES

logger = logging.getLogger(__name__)

class LighterExchange:
    def __init__(self):
        self.config = Configuration() 
        try:
             import lighter
             self.lighter_module = lighter # Store module for AccountApi usage
        except:
             self.lighter_module = None
        
        # Note: If Config.LIGHTER_API_URL exists, use it.
        
        self.api_client = ApiClient(self.config)
        self.funding_api = FundingApi(self.api_client)
        
        # Initialize SignerClient for trading
        pk = Config.LIGHTER_PRIVATE_KEY
        if pk.startswith("0x"):
            pk = pk[2:]
            
        try:
            idx = Config.LIGHTER_API_KEY_INDEX
            self.client = SignerClient(
                url=self.config.host, 
                account_index=idx, 
                api_private_keys={idx: pk}
            )
        except Exception as e:
            if Config.DRY_RUN:
                logger.warning(f"SignerClient init failed (ignored in Dry Run): {e}")
                self.client = None
            else:
                raise e
        
        self.market_map = {} 

    async def get_funding_rate(self, symbol: str):
        """
        Fetch funding rate for the symbol.
        """
        try:
            response = await self.funding_api.funding_rates()
            return response
        except Exception as e:
            logger.error(f"Error fetching Lighter funding rate: {e}")
            return None

    async def get_all_tickers(self):
        """
        Fetch all tickers/rates.
        """
        return await self.get_funding_rate("ALL")

    async def ensure_market_map(self):
        """
        Loads the market map from constants.
        """
        try:
            if not self.market_map:
                for symbol, mid in LIGHTER_MARKET_IDS.items():
                    self.market_map[symbol] = mid
                    
                for alias, target in SYMBOL_ALIASES.items():
                    if target in self.market_map:
                        self.market_map[alias] = self.market_map[target]
                
                logger.info(f"Loaded {len(self.market_map)} Lighter Markets from constants.")
        except Exception as e:
            logger.error(f"Error updating Lighter market map: {e}")

    async def place_market_order(self, symbol: str, side: str, amount: float, is_hedge: bool = True):
        try:
            await self.ensure_market_map()
            market_index = self.market_map.get(symbol, 0) 
            
            # Quantize amount before scaling
            tick_size = 0.0001 # Default safe tick
            quantized_amount = Utils.quantize_amount(amount, tick_size)
            
            if quantized_amount <= 0:
                logger.error(f"Lighter order amount too small: {amount} -> {quantized_amount}")
                return None
            
            # Scale amount
            scaled_amount = int(quantized_amount * Config.LIGHTER_AMOUNT_SCALAR) 
            
            is_ask = (side.lower() == 'sell')
            
            # price: worst price behavior
            price = 0 if is_ask else 100000000 
            
            if Config.DRY_RUN:
                logger.info(f"[DRY RUN] Lighter Market Order: {side} {quantized_amount} (scaled: {scaled_amount}) {symbol} @ Market")
                return "dry_run_tx_hash"

            tx, tx_hash, err = await self.client.create_market_order(
                market_index=market_index,
                client_order_index=0, 
                base_amount=scaled_amount,
                avg_execution_price=price,
                is_ask=is_ask
            )
            
            if err:
                logger.error(f"Lighter Order Error: {err}")
                return None
                
            logger.info(f"Lighter Order Placed: {tx_hash}")
            return tx_hash
        except Exception as e:
             logger.error(f"Lighter Order Exception: {e}")
             return None

    async def get_balance(self):
        """
        Fetch USDC/Collateral balance and positions using AccountApi.
        """
        try:
            if Config.DRY_RUN:
                return {
                    'equity': 5000.0,
                    'available': 4000.0,
                    'positions': []
                }
            
            if not self.client or not self.lighter_module:
                 return {'equity': 0, 'available': 0, 'positions': []}

            # Use AccountApi
            acc_api = self.lighter_module.AccountApi(self.client.api_client)
            idx = getattr(self.client, 'account_index', Config.LIGHTER_API_KEY_INDEX)
            
            # Fetch account by index first
            try:
                resp = await acc_api.account(by="index", value=str(idx))
            except Exception:
                # Fallback: Fetch by Owner Address
                resp = await acc_api.account(by="owner", value=Config.LIGHTER_WALLET_ADDRESS)
            
            # Extract data from response
            if isinstance(resp, list) and resp: data = resp[0]
            elif hasattr(resp, 'accounts') and resp.accounts: data = resp.accounts[0]
            else: data = resp

            equity = float(getattr(data, 'collateral', 0))
            available = float(getattr(data, 'available_balance', equity))
            
            pos_list = []
            if hasattr(data, 'positions'):
                for p in data.positions:
                    sz = float(getattr(p, 'position', 0))
                    if sz != 0:
                        side = "LONG" if getattr(p, 'sign', 0) == 1 else "SHORT"
                        pos_list.append({
                            'symbol': getattr(p, 'symbol', ''),
                            'size': abs(sz),
                            'amount': abs(sz),
                            'side': side,
                            'entry_price': float(getattr(p, 'avg_entry_price', 0))
                        })
                        
            return {'equity': equity, 'available': available, 'positions': pos_list}
        except Exception as e:
            logger.error(f"Error fetching Lighter balance: {e}")
            return {'equity': 0, 'available': 0, 'positions': []}

    async def close(self):
        await self.api_client.close()
