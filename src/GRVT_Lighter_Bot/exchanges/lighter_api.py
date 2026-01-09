import logging
import time
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
from ..constants import LIGHTER_MARKET_IDS, SYMBOL_METADATA, SYMBOL_ALIASES

logger = logging.getLogger(__name__)

class LighterExchange:
    def __init__(self):
        self.config = Configuration()
        host = "https://mainnet.zklighter.elliot.ai" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
        self.config.host = host
        # Remove direct API key setting, as per docs, we need an auth token
        # self.config.api_key['Authorization'] = Config.LIGHTER_PUBLIC_KEY
        self.auth_token = None # Will store the generated auth token
        
        try:
             import lighter
             self.lighter_module = lighter 
        except:
             self.lighter_module = None
        
        self.client = None # Will be initialized async
        self.ws_running = False
        self.bbo_cache = {}
        self.id_map = {}
        self.ticker_map = {}
        self.market_rules = {}

    async def initialize(self):
        """
        Initializes the client, discovers account index, and loads all market data.
        """
        await self.load_markets()
        
        logging.info("Initializing LighterExchange: Discovering account and loading limits...")
        
        if not Config.LIGHTER_WALLET_ADDRESS:
            logger.warning("Lighter Wallet Address not set. Skipping Account Discovery (Monitor Mode).")
            return

        found_idx = -1
        try:
            import aiohttp
            l1_address = Config.LIGHTER_WALLET_ADDRESS
            url = f"{self.config.host}/api/v1/account?by=l1_address&value={l1_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=20) as response:
                    response.raise_for_status()
                    resp_json = await response.json()

            if resp_json and resp_json.get('accounts'):
                data = resp_json['accounts'][0]
                found_idx = int(data['index'])
                logging.info(f"Lighter Account Discovery: Found account index {found_idx} for L1 address {l1_address}")
            else:
                raise ValueError("Could not parse 'accounts' or 'index' from Lighter's /account response.")

        except Exception as e:
            logger.error(f"LighterExchange Warning: Account discovery failed ({e}).")
            return

        pk = Config.LIGHTER_PRIVATE_KEY
        if not pk:
            logger.warning("Lighter Private Key missing. SignerClient will not be initialized.")
            return

        if pk.startswith("0x"): pk = pk[2:]
        
        try:
            import inspect
            sig = inspect.signature(self.lighter_module.SignerClient)
            init_kwargs = { "url": self.config.host, "account_index": found_idx, "api_private_keys": {Config.LIGHTER_API_KEY_INDEX: pk} }
            valid_kwargs = {k: v for k, v in init_kwargs.items() if k in sig.parameters}
            self.client = self.lighter_module.SignerClient(**valid_kwargs)
            logger.info(f"LighterExchange SignerClient initialized (Account: {found_idx}).")

            # Generate auth token and configure ApiClient
            try:
                auth_token_result = self.client.create_auth_token_with_expiry()
                logger.debug(f"Raw Lighter auth token result: {auth_token_result}") # Debug log
                
                # auth_token_result is typically (token, error_message)
                # Check for length and then for an error message in the second element
                if auth_token_result and len(auth_token_result) > 1 and auth_token_result[1]: # auth_token_result[1] would be the error
                    logger.error(f"Failed to generate Lighter auth token: {auth_token_result[1]}")
                elif auth_token_result and len(auth_token_result) > 0 and auth_token_result[0]: # auth_token_result[0] would be the token
                    self.auth_token = auth_token_result[0]
                    self.config.access_token = self.auth_token
                    logger.info("Lighter auth token generated and configured for API client.")
                else:
                    logger.error(f"Failed to generate Lighter auth token: Unknown error or empty result: {auth_token_result}")
            except Exception as e:
                logger.error(f"Error generating Lighter auth token: {e}", exc_info=True)

            # await self.load_leverage_limits(found_idx) # Commented out due to model mismatch
        except Exception as e:
             logger.error(f"Failed to init SignerClient or load leverage limits: {e}.")

    async def load_markets(self) -> set:
        """
        Fetches market data from two separate endpoints to build a comprehensive map of
        market IDs, symbols, and trading rules. Returns a set of available symbols.
        """
        logger.info("Loading Lighter markets and rules...")
        available_symbols = set()
        self.id_map.clear()
        self.ticker_map.clear()
        self.market_rules.clear()

        try:
            # First, get all possible markets from the explorer to populate id_map
            explorer_url = "https://explorer.elliot.ai/api/markets"
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(explorer_url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    markets_data = await response.json()
            
            for item in markets_data:
                symbol = item.get('symbol', '').split('/')[0]
                market_id = item.get('market_index')
                if symbol and market_id is not None:
                    self.id_map[market_id] = symbol
                    available_symbols.add(symbol)
            logger.info(f"[Lighter] Mapped {len(self.id_map)} symbols from explorer API for id_map.")

            # Now, get the tradable orderbooks to get correct perp trading IDs
            orderbooks_url = f"{self.config.host}/api/v1/orderBooks"
            async with aiohttp.ClientSession() as session:
                async with session.get(orderbooks_url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    orderbooks_data = await response.json()

            if orderbooks_data and 'order_books' in orderbooks_data:
                for item in orderbooks_data.get('order_books', []):
                    # logger.debug(f"Lighter orderbook item: {item}")
                    if item.get('market_type') == 'perp':
                        logger.info(f"PERP MARKET ITEM: {json.dumps(item, indent=2)}") # Log full item for inspection
                        ticker = item.get('symbol', '').split('-')[0].split('/')[0]
                        market_id_for_trading = item.get('market_id')

                        if ticker and market_id_for_trading is not None:
                            self.ticker_map[ticker] = market_id_for_trading
                            self.market_rules.setdefault(ticker, {})
                            
                            decimals = item.get('supported_size_decimals')
                            if decimals is not None:
                                min_qty = 10**(-int(decimals))
                                self.market_rules[ticker]['min_qty'] = f"{min_qty:.{decimals}f}" if decimals > 0 else str(int(min_qty))
                            else:
                                decimals = 0 # Default to 0 if not found, though risky
                                self.market_rules[ticker]['min_qty'] = item.get('min_base_amount', '0.001')
                            
                            self.market_rules[ticker]['decimals'] = int(decimals) if decimals is not None else 18 # Default to 18 if completely missing? Or 0? Let's check logic.
                            if decimals is None:
                                self.market_rules[ticker]['decimals'] = 18 # Fallback
                            else:
                                self.market_rules[ticker]['decimals'] = int(decimals)

                            price_decimals = item.get('supported_price_decimals')
                            self.market_rules[ticker]['price_decimals'] = int(price_decimals) if price_decimals is not None else 2 # Default 2

                            self.market_rules[ticker]['max_leverage'] = 'N/A'
                
                logger.info(f"[Lighter] Loaded trading rules for {len(self.market_rules)} perp markets.")
                logger.info(f"[Lighter] Loaded market rule keys: {list(self.market_rules.keys())}")
                logger.info(f"[Lighter] Final ticker map for perp trading: {self.ticker_map}")
        except Exception as e:
            logger.error(f"[Lighter] Failed to load market data: {e}")
        
        return available_symbols

    # async def load_leverage_limits(self, account_index: int):
    #     """
    #     Fetches per-market leverage limits from the authenticated /accountLimits endpoint.
    #     """
    #     if not self.client:
    #         logger.warning("Cannot load leverage limits, client not authenticated.")
    #         return
        
    #     logger.info(f"Loading leverage limits for Lighter account {account_index}...")
    #     try:
    #         account_api = self.lighter_module.AccountApi(self.client.api_client)
    #         limits_response = await account_api.account_limits(account_index=account_index, authorization=self.auth_token)
    #         logger.debug(f"Raw Lighter account_limits response: {limits_response}") # Debug log
    #         if limits_response and limits_response.limits:
    #             for limit in limits_response.limits:
    #                 ticker = self.id_map.get(limit.market_id)
    #                 if ticker and limit.max_leverage:
    #                     self.market_rules.setdefault(ticker, {})
    #                     self.market_rules[ticker]['max_leverage'] = limit.max_leverage
    #             logger.info(f"Updated Lighter leverage limits for {len(limits_response.limits)} markets.")
    #     except Exception as e:
    #         logger.error(f"Failed to load Lighter leverage limits from API: {e}")

    async def get_ticker_info(self, symbol):
        """
        Retrieves cached ticker information, prioritizing manual overrides from constants.
        """
        # 1. Check for user-defined overrides first, this is the ultimate source of truth
        if symbol in SYMBOL_METADATA:
            logger.debug(f"Using manual override for {symbol} from SYMBOL_METADATA.")
            return SYMBOL_METADATA[symbol]

        # 2. If no override, use API-driven cache
        base_symbol = symbol.split('-')[0]
        rules = self.market_rules.get(base_symbol, {})
        
        current_leverage = 'N/A'
        # Attempt to get current leverage from account positions
        if self.client:
            try:
                l1_address = Config.LIGHTER_WALLET_ADDRESS
                url = f"{self.config.host}/api/v1/account?by=l1_address&value={l1_address}"
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers={"accept": "application/json"}, timeout=5) as response:
                        response.raise_for_status()
                        resp_json = await response.json()

                if resp_json and resp_json.get('accounts'):
                    target_account = next((acc for acc in resp_json['accounts'] if int(acc.get('index', -1)) == self.client.account_index), None)
                    if target_account and 'positions' in target_account:
                        for p in target_account['positions']:
                            pos_symbol = p.get('symbol')
                            if pos_symbol == base_symbol:
                                imf_str = p.get('initial_margin_fraction')
                                if imf_str:
                                    try:
                                        current_leverage = 100 / float(imf_str)
                                    except (ValueError, ZeroDivisionError):
                                        pass
                                break
            except Exception as e:
                logger.warning(f"Could not fetch current leverage for Lighter {symbol}: {e}")

        return {
            "min_qty": rules.get('min_qty', 'N/A'),
            "max_leverage": rules.get('max_leverage', 'N/A'),
            "current_leverage": current_leverage
        }

    async def get_live_position_details(self, symbol):
        """
        Retrieves detailed position information including accurate leverage, margin usage, and funding rates.
        Returns a dictionary with parsed data.
        """
        base_symbol = symbol.split('-')[0]
        details = {
            "symbol": base_symbol,
            "size": 0.0,
            "entry_price": 0.0,
            "leverage": 0.0,
            "margin_used": 0.0,
            "unrealized_pnl": 0.0,
            "funding_rate": 0.0,
            "next_funding_time": "N/A"
        }

        if not self.client:
            logger.warning("Lighter client not initialized. Cannot fetch live position details.")
            return details

        # 1. Fetch Position & Account Data
        try:
            l1_address = Config.LIGHTER_WALLET_ADDRESS
            url = f"{self.config.host}/api/v1/account?by=l1_address&value={l1_address}"
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=5) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        if resp_json and resp_json.get('accounts'):
                            target_account = next((acc for acc in resp_json['accounts'] if int(acc.get('index', -1)) == self.client.account_index), None)
                            
                            if target_account and 'positions' in target_account:
                                for p in target_account['positions']:
                                    if p.get('symbol') == base_symbol:
                                        # logger.info(f"Raw Position Data for {base_symbol}: {p}") # Debug log
                                        
                                        raw_size = float(p.get('position', 0))
                                        sign = int(p.get('sign', 1))
                                        # Lighter: sign 1 for Long, -1 for Short, 0 for Flat? Let's check logs.
                                        # Log shows sign: 1 for Positive.
                                        # If raw_size is absolute, we apply sign.
                                        details['size'] = raw_size * sign
                                        
                                        details['entry_price'] = float(p.get('avg_entry_price', 0)) # Mapped from 'avg_entry_price'
                                        details['unrealized_pnl'] = float(p.get('unrealized_pnl', 0))
                                        
                                        # Calculate Leverage & Margin
                                        imf_str = p.get('initial_margin_fraction')
                                        if imf_str:
                                            try:
                                                imf = float(imf_str)
                                                if imf > 0:
                                                    details['leverage'] = round(100 / imf, 2)
                                                    # Margin Used ~= size * entry_price / leverage
                                                    details['margin_used'] = abs(details['size'] * details['entry_price'] / details['leverage'])
                                            except: pass
                                        break
        except Exception as e:
            logger.error(f"Error fetching account details for {symbol}: {e}")

        # 2. Fetch Funding Rate Info
        try:
            # Assuming FundingApi usage or simple REST endpoint if available
            market_id = self.ticker_map.get(base_symbol)
            if market_id is not None:
                # Funding Rate Endpoint (Example Structure)
                # Note: Lighter's funding rate might be in orderbook or separate endpoint
                funding_url = f"{self.config.host}/api/v1/fundingRate?market_id={market_id}" 
                # OR check if it's in orderbook snapshot
                
                async with aiohttp.ClientSession() as session:
                     async with session.get(funding_url, headers={"accept": "application/json"}, timeout=5) as fr_response:
                         if fr_response.status == 200:
                             fr_data = await fr_response.json()
                             # Parse funding data if available
                             # This depends on actual API response format which we might need to verify
                             # Let's try to get 'rate' and 'next_funding_time'
                             if 'rate' in fr_data:
                                 details['funding_rate'] = float(fr_data['rate'])
                             if 'next_funding_timestamp' in fr_data:
                                 # Convert timestamp to human readable
                                 import datetime
                                 ts = int(fr_data['next_funding_timestamp'])
                                 details['next_funding_time'] = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

        except Exception as e:
            logger.warning(f"Could not fetch funding rate for {symbol} (Optional): {e}")

        return details

    async def get_balance(self):
        if not self.client: return {'equity': 0, 'available': 0, 'positions': []}
        try:
            l1_address = Config.LIGHTER_WALLET_ADDRESS
            url = f"{self.config.host}/api/v1/account?by=l1_address&value={l1_address}"
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()

            if resp_json and resp_json.get('accounts'):
                target_account = next((acc for acc in resp_json['accounts'] if int(acc.get('index', -1)) == self.client.account_index), None)
                if not target_account: return {'equity': 0, 'available': 0, 'positions': []}

                # Fallback for Max Leverage if accountLimits failed
                if 'positions' in target_account:
                    for p in target_account['positions']:
                        symbol = p.get('symbol')
                        if symbol and self.market_rules.get(symbol, {}).get('max_leverage') is None:
                            imf_str = p.get('initial_margin_fraction')
                            if imf_str:
                                try:
                                    leverage = 100 / float(imf_str)
                                    self.market_rules[symbol]['max_leverage'] = f"{leverage:.0f}"
                                except (ValueError, ZeroDivisionError): pass
                
                return {
                    'equity': float(target_account.get('collateral', 0)),
                    'available': float(target_account.get('available_balance', 0)),
                    'positions': target_account.get('positions', [])
                }
            return {'equity': 0, 'available': 0, 'positions': []}
        except Exception as e:
            logger.error(f"Error fetching Lighter balance: {e}")
            return {'equity': 0, 'available': 0, 'positions': []}

    async def start_ws(self):
        self.ws_running = True
        ws_url = "wss://mainnet.zklighter.elliot.ai/stream" if Config.LIGHTER_ENV == "MAINNET" else "wss://testnet.zklighter.elliot.ai/stream"
        logger.info(f"[Lighter] Starting WebSocket for {len(self.id_map)} markets...")
        while self.ws_running:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=60) as ws:
                    self.ws = ws
                    for mid in self.id_map.keys():
                        await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{mid}"}))
                        await ws.send(json.dumps({"type": "subscribe", "channel": f"market_stats/{mid}"}))
                    async for msg in ws:
                        if not self.ws_running: break
                        try:
                            data = json.loads(msg)
                            if data.get('type') == 'ping': await ws.send(json.dumps({"type": "pong"})); continue
                            
                            channel = data.get('channel', '')
                            if not channel: continue
                            channel_type, mid_str = channel.split(':')
                            mid = int(mid_str)
                            ticker = self.id_map.get(mid)
                            if not ticker: continue
                            
                            self.bbo_cache.setdefault(ticker, {})
                            if channel_type == 'order_book':
                                ob = data.get('order_book', {})
                                bids, asks = ob.get('bids', []), ob.get('asks', [])
                                if bids: self.bbo_cache[ticker]['bid'] = float(bids[0]['price'])
                                if asks: self.bbo_cache[ticker]['ask'] = float(asks[0]['price'])
                            elif channel_type == 'market_stats':
                                stats = data.get('market_stats', {})
                                if stats.get('last_trade_price'): self.bbo_cache[ticker]['price'] = float(stats['last_trade_price'])
                                if stats.get('funding_rate'): self.bbo_cache[ticker]['funding_rate'] = float(stats['funding_rate'])
                                if stats.get('funding_timestamp'): self.bbo_cache[ticker]['next_funding_time'] = stats['funding_timestamp']
                        except Exception: pass
            except Exception as e:
                logger.error(f"Lighter WebSocket connection error: {e}")
                await asyncio.sleep(5)

    async def get_market_stats(self, symbol):
        # Cache usually keyed by full symbol e.g. "ETH-USDT"
        # Input symbol might be "ETH" or "ETH-USDT"
        
        # 1. Try exact match
        if symbol in self.bbo_cache:
             return self.bbo_cache[symbol]
        
        # 2. Try adding -USDT
        if not "-" in symbol:
             sym_usdt = f"{symbol}-USDT"
             if sym_usdt in self.bbo_cache:
                 return self.bbo_cache[sym_usdt]

        # 3. Try finding by base
        base = symbol.split('-')[0]
        for k, v in self.bbo_cache.items():
            if k.startswith(base + "-") or k == base:
                return v
                
        return {}

    async def close(self):
        self.ws_running = False
        if hasattr(self, 'ws') and self.ws: await self.ws.close()
        if self.client and hasattr(self.client, 'api_client'): await self.client.api_client.close()
        logger.info("LighterExchange resources closed.")

    async def set_leverage(self, symbol: str, leverage: int, margin_mode: str = 'cross'):
        """
        Sets the leverage for a given symbol.
        margin_mode can be 'cross' or 'isolated'.
        """
        if not self.client:
            logger.error("[Error] Cannot set Lighter leverage: client is not initialized.")
            return False
        
        try:
            base_symbol = symbol.split('-')[0]
            market_id = self.ticker_map.get(base_symbol)
            if market_id is None:
                # Fallback to search id_map
                for mid, sym in self.id_map.items():
                    if sym == base_symbol:
                        market_id = mid
                        break
            
            if market_id is None:
                logger.error(f"[Error] Could not find market_id for Lighter symbol {base_symbol}. Available tickers: {list(self.ticker_map.keys())}")
                return False
            
            market_index = int(market_id)

            # Convert margin_mode string to the integer expected by the SDK
            # SDK convention: 0 for cross, 1 for isolated
            mode_int = 0 if margin_mode.lower() == 'cross' else 1
            
            logger.info(f"Attempting to set Lighter leverage for {base_symbol} (ID: {market_index}) to {leverage}x with {margin_mode} ({mode_int}) margin...")
            
            # The signer_client's update_leverage method handles the API call
            # Returns: (tx, tx_hash, err)
            tx, tx_hash, err = await self.client.update_leverage(
                market_index=market_index,
                margin_mode=mode_int,
                leverage=leverage
            )

            if err:
                logger.error(f"[Error] Failed to set Lighter leverage for {base_symbol}. Error: {err}")
                return False
            
            if tx_hash:
                logger.info(f"[Success] Successfully submitted Lighter leverage update for {base_symbol}. Tx Hash: {tx_hash}")
                return True
            else:
                 logger.error(f"[Error] Failed to set Lighter leverage: No tx_hash returned (Unknown error)")
                 return False

        except Exception as e:
            logger.error(f"[Error] Error setting Lighter leverage for {symbol}: {e}", exc_info=True)
            return False

# The methods below are kept for potential future use or reference, but are not actively used by the monitor.
# They were accidentally deleted in a previous step and are restored to make the class whole.
    async def get_funding_rate(self, symbol: str):
        try:
            funding_api = self.lighter_module.FundingApi(self.api_client)
            return await funding_api.funding_rates()
        except Exception as e:
            logger.error(f"Error fetching Lighter funding rate: {e}")
            return None

    async def get_recent_trades_direct(self, market_id: int):
        try:
            host = "https://mainnet.zklighter.elliot.ai" if Config.LIGHTER_ENV == "MAINNET" else "https://testnet.zklighter.elliot.ai"
            url = f"{host}/api/v1/recentTrades?market_id={market_id}&limit=1"
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error fetching Lighter recent trades for ID {market_id}: {e}")
            return None
    
    async def _place_general_market_order(self, symbol: str, side: str, amount: float, reduce_only: bool):
        """
        Internal function to place a market order, with a reduce_only flag.
        """
        if not self.client:
            await self.initialize()
            if not self.client:
                logger.error("[Error] Cannot place Lighter order: client is not initialized.")
                return None
        
        try:
            base_symbol = symbol.split('-')[0]
            market_index = self.ticker_map.get(base_symbol)
            if market_index is None:
                logger.error(f"[Error] Could not find market_id for Lighter symbol {base_symbol}")
                return None
            
            # Generate a client_order_index based on timestamp to ensure uniqueness
            client_order_index = int(time.time() * 1000)

            # Convert amount to integer based on decimals
            decimals = self.market_rules.get(base_symbol, {}).get('decimals', 18) # Default to 18 if missing
            amount_int = int(amount * (10 ** decimals))
            
            # Calculate Price (Market Order Emulation)
            price_int = 0
            try:
                # Get Price Decimals
                price_decimals = self.market_rules.get(base_symbol, {}).get('price_decimals', 2)
                
                # Fetch Reference Price
                ref_price = None
                
                # 1. Try Cache
                cached_price = self.bbo_cache.get(base_symbol, {}).get('ask' if not reduce_only else 'bid') # Approximation
                if cached_price:
                    ref_price = cached_price
                
                # 2. If no cache, fetch OrderBook snapshot
                if not ref_price:
                    market_id = self.ticker_map.get(base_symbol)
                    if market_id is not None:
                        url = f"{self.config.host}/api/v1/orderBook?market_id={market_id}"
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                             async with session.get(url, headers={"accept": "application/json"}, timeout=5) as response:
                                 if response.status == 200:
                                     ob_data = await response.json()
                                     # logger.info(f"OrderBook Snapshot for {base_symbol}: {str(ob_data)[:200]}...") # Log start of OB
                                     
                                     # Determine generic side for price ref
                                     # For Buy (Ask), For Sell (Bid)
                                     target_side = 'asks' if (side.lower() != 'sell') else 'bids'
                                     target_list = ob_data.get(target_side, [])
                                     
                                     if target_list:
                                         ref_price = float(target_list[0]['price'])
                                     else:
                                         logger.warning(f"OrderBook {target_side} empty for {base_symbol}. Full OB keys: {ob_data.keys()}")
                                 else:
                                     logger.warning(f"Failed to fetch OrderBook for {base_symbol}: Status {response.status}")
                
                # 3. Fallback to hardcoded safe values if still None (Network error etc)
                if not ref_price:
                    logger.warning(f"Using Fallback Price for {base_symbol} (Market Data missing)")
                    # Very conservative fallback
                    # BTC ~100k, ETH ~3k
                    if 'BTC' in base_symbol: ref_price = 200000 if side.lower() != 'sell' else 1
                    elif 'ETH' in base_symbol: ref_price = 10000 if side.lower() != 'sell' else 1
                    else: ref_price = 1000000 if side.lower() != 'sell' else 1 # Generic
                
                # Apply Slippage (5%)
                if side.lower() != 'sell':
                    final_price = ref_price * 1.05
                else:
                    final_price = ref_price * 0.95
                
                # Convert to integer
                price_int = int(final_price * (10 ** price_decimals))
                if price_int < 1: price_int = 1 # Minimum 1
                
                logger.info(f"Market Order {base_symbol} {side}: Ref Price {ref_price}, Final Price {final_price}, Int Price {price_int}")

            except Exception as px:
                logger.error(f"Error calculating market price: {px}")
                # Fallback to safe int
                price_int = 1000000000 if side.lower() != 'sell' else 1

            # Using the general `create_order` to pass the `reduce_only` flag.
            # For market orders, price is 0, and time_in_force is IMMEDIATE_OR_CANCEL.
            tx, tx_hash, err = await self.client.create_order(
                market_index=int(market_index),
                is_ask=(side.lower() == 'sell'),
                base_amount=amount_int,
                price=price_int, # Send calculated price
                order_type=self.client.ORDER_TYPE_MARKET,
                time_in_force=self.client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
                reduce_only=reduce_only,
                client_order_index=client_order_index,
                order_expiry=0 # Must be 0 for IOC orders
            )

            if err:
                logger.error(f"[Error] Lighter Order Error: {err}")
                return None
            
            return tx_hash
        except Exception as e:
             logger.error(f"[Error] Lighter Order Exception: {e}", exc_info=True)
             return None

    async def place_market_order(self, symbol: str, side: str, amount: float):
        """Places a standard market order to open or increase a position."""
        logger.info(f"Placing new market order: {side.upper()} {amount} {symbol}")
        return await self._place_general_market_order(symbol, side, amount, reduce_only=False)

    async def close_market_position(self, symbol: str, side: str, amount: float):
        """Places a reduce-only market order to close or decrease a position."""
        logger.info(f"Placing REDUCE-ONLY market order: {side.upper()} {amount} {symbol}")
        return await self._place_general_market_order(symbol, side, amount, reduce_only=True)

