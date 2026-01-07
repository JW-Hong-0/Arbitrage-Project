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
        
        self.client = None # Will be initialized async
        self.market_map = {} 

    async def initialize(self):
        """
        Initializes the SignerClient after discovering the account index via a direct, non-blocking API call
        with a hardcoded, known-good URL.
        """
        logging.info("Initializing LighterExchange: Discovering account via direct API call...")
        
        if not Config.LIGHTER_WALLET_ADDRESS:
            raise ConnectionError("LighterExchange Error: LIGHTER_WALLET_ADDRESS must be set in config.")

        found_idx = -1
        try:
            import aiohttp
            l1_address = Config.LIGHTER_WALLET_ADDRESS
            # Hardcode the known-good URL to prevent any host resolution issues.
            url = f"https://testnet.zklighter.elliot.ai/api/v1/account?by=l1_address&value={l1_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=20) as response:
                    response.raise_for_status()
                    resp_json = await response.json()

            if resp_json and resp_json.get('accounts'):
                data = resp_json['accounts'][0]
                found_idx = int(data['index'])
                logging.info(f"✅ Lighter Account Discovery: Found account index {found_idx} for L1 address {l1_address}")
            else:
                raise ValueError(f"Could not parse 'accounts' or 'index' from direct API response: {resp_json}")

        except Exception as e:
            raise ConnectionError(f"LighterExchange Error: Failed to fetch account via direct API call. {e}")

        pk = Config.LIGHTER_PRIVATE_KEY
        if pk.startswith("0x"):
            pk = pk[2:]
        api_key_idx = Config.LIGHTER_API_KEY_INDEX

        self.client = SignerClient(
            url=self.config.host, # This host is for the SignerClient, which might be different. Defaulting to SDK's is safer.
            account_index=found_idx,
            api_private_keys={api_key_idx: pk}
        )
        logger.info(f"LighterExchange initialized successfully with SignerClient (Account: {found_idx}, Key Index: {api_key_idx}).")


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
            if not self.client: await self.initialize()
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
        Fetch USDC/Collateral balance by bypassing the buggy SDK and using a direct, non-blocking aiohttp call.
        """
        try:
            if Config.DRY_RUN:
                return {'equity': 5000.0, 'available': 4000.0, 'positions': []}
            
            if not self.client:
                 raise ConnectionError("LighterExchange not initialized. Call initialize() first.")

            l1_address = Config.LIGHTER_WALLET_ADDRESS
            if not l1_address:
                raise ValueError("LIGHTER_WALLET_ADDRESS not set, cannot fetch balance.")

            url = f"{self.client.api_client.configuration.host}/api/v1/account?by=l1_address&value={l1_address}"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()

            if resp_json and resp_json.get('accounts'):
                data = resp_json['accounts'][0]
                equity = float(data.get('collateral', 0))
                available = float(data.get('available_balance', equity))
                
                pos_list = []
                if 'positions' in data:
                    for p in data['positions']:
                        sz = float(p.get('position', 0))
                        if sz != 0:
                            side = "LONG" if float(p.get('sign', 1)) > 0 else "SHORT"
                            pos_list.append({
                                'symbol': p.get('symbol', ''),
                                'size': abs(sz), 'amount': abs(sz), 'side': side,
                                'entry_price': float(p.get('avg_entry_price', 0))
                            })
                return {'equity': equity, 'available': available, 'positions': pos_list}
            else:
                raise ValueError(f"Could not parse 'accounts' from direct API response: {resp_json}")

        except Exception as e:
            logger.error(f"Error fetching Lighter balance via direct API call: {e}")
            return {'equity': 0, 'available': 0, 'positions': []}

    async def close(self):
        await self.api_client.close()
        if self.client:
            # Assuming the signer client uses the same underlying api_client
            # If it has its own session, it should be closed here.
            pass


