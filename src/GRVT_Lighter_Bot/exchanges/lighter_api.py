import logging
import asyncio
from lighter.api.funding_api import FundingApi
from lighter.api_client import ApiClient
from lighter.configuration import Configuration
from lighter.models.funding_rates import FundingRates

# Assume config is available or passed in
from ..config import Config

logger = logging.getLogger(__name__)

import logging
import asyncio
from lighter.api.funding_api import FundingApi
from lighter.api_client import ApiClient
from lighter.configuration import Configuration
from lighter.models.funding_rates import FundingRates
from lighter.signer_client import SignerClient
from ..config import Config

logger = logging.getLogger(__name__)

class LighterExchange:
    def __init__(self):
        # Use SDK default host if not provided, or a specific Lighter API URL.
        # RPC URL provided by user is for Web3, not Lighter REST API usually.
        # But for now, if the SDK requires it, we'll use default.
        self.config = Configuration() 
        # Note: If Config.LIGHTER_API_URL exists, use it.
        
        self.api_client = ApiClient(self.config)
        self.funding_api = FundingApi(self.api_client)
        
        # Initialize SignerClient for trading
        # Expecting private key in hex
        pk = Config.LIGHTER_PRIVATE_KEY
        if pk.startswith("0x"):
            pk = pk[2:]
            
        self.client = SignerClient(
            url=self.config.host, # Use the host from configuration
            account_index=0, # Assuming index 0
            api_private_keys={0: pk}
        )
        
        self.market_map = {} # Symbol -> MarketIndex

    async def get_funding_rate(self, symbol: str):
        """
        Fetch funding rate for the symbol.
        """
        try:
            # API returns all rates usually
            response = await self.funding_api.funding_rates()
            # Response likely has a list of rates.
            # We need to map symbol (e.g. BTC-USDT) to Lighter ID or symbol
            # For now, returning the raw list or a dict if possible
            return response
        except Exception as e:
            logger.error(f"Error fetching Lighter funding rate: {e}")
            return None

    async def get_all_tickers(self):
        # Lighter might not have a simple "all tickers" endpoint in this API class
        # But funding_rates() returns rates for all markets.
        # We can use that as a proxy for available markets for FR scanning.
        return await self.get_funding_rate("ALL")

    async def ensure_market_map(self):
        if not self.market_map:
            try:
                # Fetch markets/orderbooks to map symbol to index
                # This depends on available API. Using funding rates or info if possible.
                # Assuming funding rates return market info
                # Or use basic hardcoded for common pairs for Phase 1 if API is opaque
                # But let's try to be dynamic if possible.
                # TODO: Implement proper mapping. For now, forcing BTC-USDT = 0 (Example)
                self.market_map = {"BTC-USDT": 0, "ETH-USDT": 1} 
            except Exception as e:
                logger.error(f"Error mapping markets: {e}")

    async def place_market_order(self, symbol: str, side: str, amount: float, is_hedge: bool = True):
        try:
            await self.ensure_market_map()
            market_index = self.market_map.get(symbol, 0) # Default to 0 (ETH-USDC usually) if unknown
            
            # Amount handling: Lighter uses specific units (e.g. 0.001 ETH might be 1000)
            # We need to know the size tick.
            # For Phase 1 demo/dry-run, we assume amount is passed correctly or scaled.
            # Base amount logic from example: 0.1 ETH = 1000 -> scale 10000? 
            # Example says: base_amount=1000 # 0.1 ETH. So 1 = 0.0001 ETH? 
            # We will use raw amount for now or add a scaler config.
            
            scaled_amount = int(amount * 10000) # Placeholder scaler
            
            is_ask = (side.lower() == 'sell')
            
            # price: worst price. Market order needs a limit/protection.
            # If buying, high price; if selling, low price (0).
            # Example uses avg_execution_price.
            price = 0 if is_ask else 100000000 # Max price
            
            tx, tx_hash, err = await self.client.create_market_order(
                market_index=market_index,
                client_order_index=0, # Should increment or use random? SDK might handle?
                # SDK create_market_order usually handles nonce if not passed? 
                # Example passed 0.
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

    async def close(self):
        await self.api_client.close()

