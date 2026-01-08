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
            await self.load_leverage_limits(found_idx)
        except Exception as e:
             logger.error(f"Failed to init SignerClient or load leverage limits: {e}.")

    async def load_markets(self) -> set:
        """
        Fetches market data from two separate endpoints to build a comprehensive map of
        market IDs, symbols, and trading rules. Returns a set of available symbols.
        """
        logger.info("Loading Lighter markets and rules...")
        available_symbols = set()
        try:
            explorer_url = "https://explorer.elliot.ai/api/markets"
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(explorer_url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    markets_data = await response.json()
            
            self.id_map.clear(); self.ticker_map.clear()
            for item in markets_data:
                symbol = item.get('symbol', '').split('/')[0]
                market_id = item.get('market_index')
                if symbol and market_id is not None:
                    self.id_map[market_id] = symbol
                    self.ticker_map[symbol] = symbol
                    available_symbols.add(symbol)
            logger.info(f"[Lighter] Mapped {len(self.ticker_map)} symbols from explorer API.")

            orderbooks_url = f"{self.config.host}/api/v1/orderBooks"
            async with aiohttp.ClientSession() as session:
                async with session.get(orderbooks_url, headers={"accept": "application/json"}, timeout=10) as response:
                    response.raise_for_status()
                    orderbooks_data = await response.json()

            if orderbooks_data and 'order_books' in orderbooks_data:
                self.market_rules.clear()
                for item in orderbooks_data.get('order_books', []):
                    ticker = item.get('symbol', '').split('-')[0]
                    if ticker in self.ticker_map:
                        self.market_rules.setdefault(ticker, {})
                        
                        decimals = item.get('supported_size_decimals')
                        if decimals is not None:
                            min_qty = 10**(-int(decimals))
                            self.market_rules[ticker]['min_qty'] = f"{min_qty:.{decimals}f}" if decimals > 0 else str(int(min_qty))
                        else:
                            self.market_rules[ticker]['min_qty'] = item.get('min_base_amount', '0.001')

                        self.market_rules[ticker]['max_leverage'] = 'N/A'
                logger.info(f"[Lighter] Loaded trading rules for {len(self.market_rules)} markets.")
        except Exception as e:
            logger.error(f"[Lighter] Failed to load market data: {e}")
        
        return available_symbols

    async def load_leverage_limits(self, account_index: int):
        """
        Fetches per-market leverage limits from the authenticated /accountLimits endpoint.
        """
        if not self.client:
            logger.warning("Cannot load leverage limits, client not authenticated.")
            return
        
        logger.info(f"Loading leverage limits for Lighter account {account_index}...")
        try:
            account_api = self.lighter_module.AccountApi(self.client.api_client)
            limits_response = await account_api.account_limits(account_index=account_index)

            if limits_response and limits_response.limits:
                for limit in limits_response.limits:
                    ticker = self.id_map.get(limit.market_id)
                    if ticker and limit.max_leverage:
                        self.market_rules.setdefault(ticker, {})
                        self.market_rules[ticker]['max_leverage'] = limit.max_leverage
                logger.info(f"Updated Lighter leverage limits for {len(limits_response.limits)} markets.")
        except Exception as e:
            logger.error(f"Failed to load Lighter leverage limits from API: {e}")

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
        
        return {
            "min_qty": rules.get('min_qty', 'N/A'),
            "max_leverage": rules.get('max_leverage', 'N/A')
        }

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
        base_symbol = symbol.split('-')[0]
        return self.bbo_cache.get(base_symbol, {})

    async def close(self):
        self.ws_running = False
        if hasattr(self, 'ws') and self.ws: await self.ws.close()
        if self.client and hasattr(self.client, 'api_client'): await self.client.api_client.close()
        logger.info("LighterExchange resources closed.")

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
    
    async def place_market_order(self, symbol: str, side: str, amount: float, is_hedge: bool = True):
        try:
            if not self.client: await self.initialize()
            base_symbol = symbol.split('-')[0]
            market_index = self.ticker_map.get(base_symbol)
            if not market_index: return None
            
            quantized_amount = Utils.quantize_amount(amount, 0.0001)
            if quantized_amount <= 0: return None
            
            scaled_amount = int(quantized_amount * Config.LIGHTER_AMOUNT_SCALAR) 
            is_ask = (side.lower() == 'sell')
            price = 0 if is_ask else 100000000 
            
            _, tx_hash, err = await self.client.create_market_order(market_index=market_index, client_order_index=0, base_amount=scaled_amount, avg_execution_price=price, is_ask=is_ask)
            if err: logger.error(f"Lighter Order Error: {err}"); return None
            return tx_hash
        except Exception as e:
             logger.error(f"Lighter Order Exception: {e}")
             return None
