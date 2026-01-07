import logging

import json
import websockets
import asyncio
from lighter.api.funding_api import FundingApi
from lighter.api.order_api import OrderApi
from lighter.api_client import ApiClient
from lighter.configuration import Configuration
from lighter.models.funding_rates import FundingRates
from lighter.signer_client import SignerClient
from ..config import Config
from ..utils import Utils
from ..constants import LIGHTER_MARKET_IDS, SYMBOL_ALIASES

logger = logging.getLogger(__name__)

class LighterWS:
    def __init__(self, market_id, callback):
        self.market_id = market_id
        self.callback = callback
        self.ws_url = "wss://api.lighter.xyz/ws" if Config.LIGHTER_ENV == "MAINNET" else "wss://api.testnet.zklighter.elliot.ai/ws" # Update based on standard or config
        # Verify testnet WS URL from docs if possible, or assume based on api host.
        # User provided example subscription JSON, implying standard WS.
        # "wss://" + host.replace("https://", "")
        self.running = False
        self.ws = None

    async def start(self):
        self.running = True
        asyncio.create_task(self._run())

    async def _run(self):
        while self.running:
            try:
                # Use the exact host from Config logic, stripping protocol
                base_host = "api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "testnet.zklighter.elliot.ai"
                # SDK Client uses /stream by default.
                ws_url = f"wss://{base_host}/stream"
                
                logger.info(f"Connecting to Lighter WS: {ws_url}")
                async with websockets.connect(ws_url) as ws:
                    self.ws = ws
                    # Subscribe
                    sub_msg = {
                        "type": "subscribe",
                        "channel": f"market_stats/{self.market_id}"
                    }
                    await ws.send(json.dumps(sub_msg))
                    logger.info(f"Subscribed to market_stats/{self.market_id}")
                    
                    while self.running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get("type") == "update/market_stats":
                            await self.callback(data.get("market_stats", {}))
                        elif data.get("type") == "ping":
                            await ws.send(json.dumps({"type": "pong"}))
            except Exception as e:
                logger.error(f"Lighter WS Error: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()

class LighterExchange:
    def __init__(self):
        self.config = Configuration()
        host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
        self.config.host = host
        
        try:
             import lighter
             self.lighter_module = lighter 
        except:
             self.lighter_module = None
        
        self.api_client = ApiClient(self.config)
        self.funding_api = FundingApi(self.api_client)
        self.order_api = OrderApi(self.api_client)
        
        self.client = None # Will be initialized async
        self.market_map = {} 
        self.ws = None
        self.latest_market_stats = {}

    async def _on_market_stats(self, stats):
        # Callback to update local cache
        self.latest_market_stats = stats
        # logger.info(f"Updated Lighter Market Stats via WS: {stats}") 

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
            # Dynamically select host based on environment
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/account?by=l1_address&value={l1_address}"
            
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
        Fetch all tickers/rates. Now uses direct API call.
        """
        return await self.get_funding_rates_direct()

    async def get_funding_rates_direct(self):
        """
        Fetch funding rates by bypassing the SDK and using a direct, non-blocking aiohttp call.
        """
        try:
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/funding-rates"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()
                    return resp_json.get('funding_rates', [])
        except Exception as e:
            logger.error(f"Error fetching Lighter funding rates via direct API call: {e}")
            return None

    async def get_orderbook_direct(self, market_id: int):
        """
        Fetch order book (best bid/ask) for a market_id.
        """
        try:
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/orderBookOrders?market_id={market_id}&limit=1"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error fetching Lighter order book for ID {market_id}: {e}")
            return None

    async def get_recent_trades_direct(self, market_id: int):
        """
        Fetch recent trades (last price) for a market_id.
        """
        try:
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/recentTrades?market_id={market_id}&limit=1"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error fetching Lighter recent trades for ID {market_id}: {e}")
            return None

    async def get_orderbook_details_direct(self, market_id: int):
        """
        Fetch order book details (min size) for a market_id.
        """
        try:
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/orderBookDetails?market_id={market_id}"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error fetching Lighter order book details for ID {market_id}: {e}")
            return None

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

            # Dynamically select host based on environment
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/account?by=l1_address&value={l1_address}"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()

            if resp_json and resp_json.get('accounts'):
                # Filter by correct index if possible, otherwise take the first one or sum valid ones
                target_index = Config.LIGHTER_API_KEY_INDEX
                target_account = None
                
                for acc in resp_json['accounts']:
                    if int(acc.get('index', -1)) == target_index:
                        target_account = acc
                        break
                
                # Fallback to first one if not found (or log warning)
                if not target_account:
                    logger.warning(f"Account with index {target_index} not found in Lighter response. Using first account.")
                    target_account = resp_json['accounts'][0]

                data = target_account
                equity = float(data.get('collateral', 0))
                available = float(data.get('available_balance', equity))
                
                pos_list = []
                if 'positions' in data:
                    for p in data['positions']:
                        sz = float(p.get('position', 0))
                        if sz != 0:
                            side = "LONG" if float(p.get('sign', 1)) > 0 else "SHORT"
                            pos_list.append({
                                'symbol': p.get('symbol', ''), # The API might return ID, need to map back if needed
                                'size': abs(sz), 'amount': abs(sz), 'side': side,
                                'entry_price': float(p.get('avg_entry_price', 0))
                            })
                return {'equity': equity, 'available': available, 'positions': pos_list}
            else:
                raise ValueError(f"Could not parse 'accounts' from direct API response: {resp_json}")

        except Exception as e:
            logger.error(f"Error fetching Lighter balance via direct API call: {e}")
            return {'equity': 0, 'available': 0, 'positions': []}

    async def get_ticker_info(self, symbol):
        """
        Retrieves ticker information.
        """
        try:
            # For Lighter, we might need to query 'markets' or hardcode if API didn't expose it easily.
            # Using direct REST call to get market details.
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/markets"
             
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=5) as response:
                    # response.raise_for_status() # Optional, some APIs might error on global list
                    if response.status == 200:
                        mkts = await response.json()
                        # Find our symbol
                        # Map symbol (BTC-USDT) to what Lighter expects?
                        # Likely they return a list of objects with 'id', 'symbol', 'min_order_size' etc.
                        
                        # Placeholder logic pending API verification
                        target_id = None 
                        # Resolve ID
                        base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
                        if base_symbol in SYMBOL_ALIASES:
                            base_symbol = SYMBOL_ALIASES[base_symbol]
                        
                        if base_symbol in LIGHTER_MARKET_IDS:
                            target_id = LIGHTER_MARKET_IDS[base_symbol]
                            
                        # If we can parse mkts
                        if isinstance(mkts, list):
                            for m in mkts:
                                if m.get('market_id') == target_id or m.get('symbol') == base_symbol:
                                    return {
                                        "min_qty": m.get('min_order_size'),
                                        "max_leverage": m.get('max_leverage', 10), # Default likely 10-20
                                        "tick_size": m.get('tick_size')
                                    }
            
            return {"min_qty": "0.0001", "max_leverage": "50"} # Fallback defaults for user requirement
        except Exception as e:
            logger.error(f"Error fetching Lighter ticker info: {e}")
            return None

    async def get_funding_info(self, symbol):
        """
        Fetches funding rate.
        """
        try:
            # Determine Market ID
            base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
            if base_symbol in SYMBOL_ALIASES:
                base_symbol = SYMBOL_ALIASES[base_symbol]
            market_id = LIGHTER_MARKET_IDS.get(base_symbol, 0)

            # Direct API call for funding
            host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/funding-rates?market_id={market_id}"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Depending on structure: { 'rate': ..., 'next_funding': ... } or list
                        # Assuming Lighter returns current rate
                        if isinstance(data, dict):
                            return {
                                "funding_rate": data.get('rate') or data.get('funding_rate'),
                                "next_funding_time": data.get('next_funding_time') or data.get('timestamp'),
                                "mark_price": None
                            }
                        elif isinstance(data, list) and len(data) > 0:
                             # If list of history, take latest? Or list of markets?
                             # Assuming list of markets if market_id param wasn't respected, or list of rates.
                             pass
            
            return {"funding_rate": None, "next_funding_time": None}
        except Exception as e:
            # logger.warning(f"Error fetching Lighter funding info: {e}")
            return {"funding_rate": None, "next_funding_time": None}

    async def get_market_stats(self, symbol):
        """
        Fetches market stats using WS cache if available, else falls back to SDK/REST.
        """
        try:
            # Determine Market ID
            base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
            if base_symbol in SYMBOL_ALIASES:
                base_symbol = SYMBOL_ALIASES[base_symbol]
            market_id = LIGHTER_MARKET_IDS.get(base_symbol, 0)
            
            # Start WS if not running
            if not self.ws:
                self.ws = LighterWS(market_id, self._on_market_stats)
                await self.ws.start()
            
            # Prefer WS Data
            ws_stats = self.latest_market_stats
            
            price = ws_stats.get('last_trade_price')
            mark_price = ws_stats.get('mark_price')
            funding_rate = ws_stats.get('funding_rate')
            next_funding_time = ws_stats.get('funding_timestamp')
            
            # 1. Get Price via SDK (Fallback)
            if not price:
                try:
                    # SDK Method: order_book_details
                    details = await self.order_api.order_book_details(market_id=market_id)
                    
                    if details and details.order_book_details:
                        target_detail = next((d for d in details.order_book_details if d.market_id == market_id), None)
                        if not target_detail and len(details.order_book_details) > 0:
                            target_detail = details.order_book_details[0]
                            
                        if target_detail:
                             price = str(target_detail.last_trade_price)
                except Exception as e:
                    logger.warning(f"SDK order_book_details fallback failed: {e}")
                    pass
                
            # 2. Get Funding (Fallback)
            if not funding_rate:
                try:
                    # Manual fallback using existing client
                    host = "https://api.lighter.xyz" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
                    url = f"{host}/api/v1/funding-rates"
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                         async with session.get(url, headers={"accept": "application/json"}, timeout=5) as response:
                            if response.status == 200:
                                all_rates = await response.json()
                                rates_list = all_rates.get('funding_rates', []) if isinstance(all_rates, dict) else []
                                target = next((r for r in rates_list if r.get('market_id') == market_id and r.get('exchange') == 'lighter'), None)
                                if target:
                                    funding_rate = target.get('rate')
                except Exception:
                    pass

            return {
                "price": price,
                "mark_price": mark_price or price, # Approx
                "index_price": ws_stats.get('index_price'),
                "funding_rate": funding_rate,
                "next_funding_time": next_funding_time 
            }
        except Exception as e:
            logger.error(f"Error fetching Lighter market stats: {e}")
            return None

    async def close(self):
        await self.api_client.close()
        if self.client:
            # Assuming the signer client uses the same underlying api_client
            # If it has its own session, it should be closed here.
            pass


