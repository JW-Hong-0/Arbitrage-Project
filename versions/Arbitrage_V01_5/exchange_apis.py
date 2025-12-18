import asyncio
import logging
import json
import websockets
import ssl
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable, Tuple
import sys
import time
import math
import os
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
import requests
import uuid
import inspect 

# --- [필수] Pacifica 및 공통 라이브러리 ---
try:
    import base58
    from solders.keypair import Keypair
except ImportError:
    base58 = None; Keypair = None

# --- Hyperliquid SDK ---
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange as HLExchange
    from hyperliquid.utils import constants as hl_constants
    from hyperliquid.utils.types import Cloid
    from eth_account import Account
except ImportError:
    Info = None; HLExchange = None; Cloid = None; Account = None

# --- GRVT SDK & Environment Patching ---
try:
    from pysdk.grvt_ccxt_ws import GrvtCcxtWS
    from pysdk.grvt_ccxt_env import GrvtEnv, GRVT_ENDPOINTS, GrvtEndpointType, END_POINT_VERSION, get_grvt_endpoint
    
    if "GET_ALL_INITIAL_LEVERAGE" not in GRVT_ENDPOINTS[GrvtEndpointType.TRADE_DATA]:
        GRVT_ENDPOINTS[GrvtEndpointType.TRADE_DATA]["GET_ALL_INITIAL_LEVERAGE"] = f"full/{END_POINT_VERSION}/get_all_initial_leverage"
        GRVT_ENDPOINTS[GrvtEndpointType.TRADE_DATA]["SET_INITIAL_LEVERAGE"] = f"full/{END_POINT_VERSION}/set_initial_leverage"
except ImportError:
    GrvtCcxtWS = None; GrvtEnv = None

# --- Settings & Constants ---
try:
    import settings
    PAC_SPREAD = getattr(settings, 'PACIFICA_VIRTUAL_SPREAD', 0.0005)
except ImportError:
    settings = None; PAC_SPREAD = 0.0005 

# [수정] GRVT 및 WebSocket 소음 강력 차단
LOG_BLOCK_LIST = [
    "pysdk", "GrvtCcxtWS", "GrvtCcxtBase", "grvt_ccxt_ws", "grvt_ccxt_pro",
    "websockets", "asyncio", "urllib3", "requests", "MARKET_SYNC"
]
for logger_name in LOG_BLOCK_LIST:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

log = logging.getLogger("ExchangeAPIs")
log.setLevel(logging.INFO)

BASED_BUILDER_ADDRESS = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
BASED_CLOID_STR = "0xba5ed11067f2cc08ba5ed10000ba5ed1"

class Exchange(ABC):
    def __init__(self):
        self.ws_running = False
        self.bbo_cache = {} 
        self.last_log_time = 0
        self.last_prices = {} 
        self.market_info = {} 

    @abstractmethod
    async def start_ws(self, callback: Callable): pass

    def get_bbo(self, ticker: str) -> Optional[Dict]:
        return self.bbo_cache.get(ticker)

    async def close(self):
        self.ws_running = False
        
    def _log_heartbeat(self, exchange_name, ticker, price):
        if time.time() - self.last_log_time > 10:
            log.info(f"💓 [{exchange_name}] {ticker} Mid: ${price:.4f}")
            self.last_log_time = time.time()

    def _validate_and_format(self, exchange, symbol, bid, ask, bid_qty=0.0, ask_qty=0.0):
        if bid <= 0 or ask <= 0: return None
        if bid >= ask: return None
        current_mid = (bid + ask) / 2
        last_price = self.last_prices.get(symbol)
        if last_price and abs(current_mid - last_price) / last_price > 0.05: return None
        self.last_prices[symbol] = current_mid
        return {
            'symbol': symbol, 'bid': bid, 'ask': ask,
            'bid_qty': bid_qty, 'ask_qty': ask_qty,
            'exchange': exchange, 'timestamp': time.time()
        }
    
    async def set_leverage(self, symbol: str, leverage: int) -> Tuple[bool, int]: pass

    @abstractmethod
    async def load_markets(self): pass

    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, amount: float, price: float = None, reduce_only: bool = False): pass

    @abstractmethod
    async def get_balance(self) -> Dict: pass

    def validate_amount(self, symbol: str, amount: float) -> float:
        base = symbol.split('_')[0].split('-')[0]
        if base.startswith('k'): base = base[1:]
        if base.startswith('1000'): base = base[4:]
        
        info = self.market_info.get(base)
        if not info: return round(amount, 4)

        prec = info.get('qty_prec', 3)
        min_sz = info.get('min_size', 0.0)

        if amount < min_sz:
            return 0.0

        if prec <= 0:
             step = 10 ** abs(prec)
             return math.floor(amount / step) * step
        else:
            factor = 10 ** prec
            return math.floor(amount * factor) / factor

# ==========================================
# 2. Hyperliquid Implementation
# ==========================================
class HyperliquidExchange(Exchange):
    def __init__(self, private_key: str):
        super().__init__()
        self.private_key = private_key
        self.agent_address = None
        self.main_address = os.getenv("HYPERLIQUID_MAIN_ADDRESS")
        self.exchange = None
        self.info = None
        
        self.ws_url = "wss://api.hyperliquid.xyz/ws"
        self.target_symbols = []
        self.reverse_map = {} 
        if settings:
            for ticker, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'hyperliquid' in cfg['symbols']:
                    hl_sym = cfg['symbols']['hyperliquid']
                    if hl_sym:
                        self.target_symbols.append(hl_sym)
                        self.reverse_map[hl_sym] = ticker 
                        if hl_sym.startswith('k'): self.reverse_map[hl_sym[1:]] = ticker
        
        if Info and self.private_key:
            try:
                account = Account.from_key(self.private_key)
                self.agent_address = account.address
                if not self.main_address: self.main_address = self.agent_address
                self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True)
                self.exchange = HLExchange(account, hl_constants.MAINNET_API_URL)
                log.info(f"✅ [HL] 초기화 (Vault: {self.main_address[:6]}..)")
            except Exception as e: log.error(f"❌ [HL] 초기화 실패: {e}")

    async def load_markets(self):
        try:
            meta = self.info.meta()
            for asset in meta['universe']:
                name = asset['name']
                self.market_info[name] = {
                    'qty_prec': asset['szDecimals'],
                    'min_size': 10 ** (-asset['szDecimals']),
                    'max_lev': int(asset['maxLeverage'])
                }
            log.info(f"✅ [HL] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e: log.error(f"❌ [HL] 로드 실패: {e}")

    async def get_balance(self):
        try:
            state = self.info.user_state(self.main_address)
            margin = state.get('marginSummary', {})
            equity = float(margin.get('accountValue', 0))
            withdrawable = float(margin.get('withdrawable', 0))
            margin_used = float(margin.get('totalMarginUsed', 0))
            available = max(withdrawable, equity - margin_used)
            
            raw_positions = state.get('assetPositions', [])
            positions = []
            for p in raw_positions:
                pos_data = p.get('position', {})
                coin = pos_data.get('coin', '')
                size = float(pos_data.get('szi', 0))
                if size != 0:
                    positions.append({
                        'symbol': coin, 'size': abs(size), 'amount': abs(size),
                        'side': 'LONG' if size > 0 else 'SHORT',
                        'entry_price': float(pos_data.get('entryPx', 0))
                    })
            return {'equity': equity, 'available': available, 'positions': positions}
        except Exception as e:
            log.error(f"❌ [HL] 잔고 조회 실패: {e}")
            return None

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        is_buy = (side.upper() == 'BUY')
        if price is None: price = float(self.info.all_mids().get(symbol, 0))
        limit_px = float(f"{price * 1.05:.5g}") if is_buy else float(f"{price * 0.95:.5g}")

        order = {
            "coin": symbol, "is_buy": is_buy, "sz": val_amt, "limit_px": limit_px,
            "order_type": {"limit": {"tif": "Ioc"}}, "reduce_only": reduce_only,
            "cloid": Cloid.from_str(BASED_CLOID_STR)
        }
        try:
            res = self.exchange.bulk_orders([order], builder={"b": BASED_BUILDER_ADDRESS.lower(), "f": 25})
            if res['status'] == 'ok':
                log.info(f"✅ [HL] 주문 성공: {symbol} {side} (Reduce: {reduce_only})")
                return res
            else:
                log.error(f"❌ [HL] 주문 실패: {res}")
                return None
        except Exception as e:
            log.error(f"❌ [HL] 예외: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        try:
            self.exchange.update_leverage(leverage, symbol, is_cross=True)
            return True, leverage
        except: return False, leverage

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "allMids"}}))
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        if data.get("channel") == "allMids":
                            mids = data.get("data", {}).get("mids", {})
                            for coin, price_str in mids.items():
                                bot_symbol = self.reverse_map.get(coin) or self.reverse_map.get("k" + coin)
                                if bot_symbol:
                                    try:
                                        price = float(price_str)
                                        if price <= 0: continue
                                        bbo = self._validate_and_format('HL', bot_symbol, price*0.9995, price*1.0005)
                                        if bbo:
                                            self.bbo_cache[bot_symbol] = bbo
                                            if bot_symbol == 'BTC': self._log_heartbeat('HL', bot_symbol, price)
                                            await callback(bbo)
                                    except: pass
            except Exception as e:
                await asyncio.sleep(5)

# ==========================================
# 3. GRVT Implementation
# ==========================================
class GrvtExchange(Exchange):
    def __init__(self):
        super().__init__()
        self.grvt = None
        self.api_key = os.getenv('GRVT_API_KEY')
        self.private_key = os.getenv('GRVT_PRIVATE_KEY') or os.getenv('GRVT_SECRET_KEY')
        self.sub_account_id = os.getenv('GRVT_TRADING_ACCOUNT_ID')

        if GrvtCcxtWS:
            try:
                loop = asyncio.get_running_loop()
            except: 
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            params = {'api_key': self.api_key, 'private_key': self.private_key, 'trading_account_id': self.sub_account_id}
            try:
                quiet = logging.getLogger("quiet_grvt")
                quiet.setLevel(logging.CRITICAL)
                self.grvt = GrvtCcxtWS(env=GrvtEnv.PROD, loop=loop, parameters=params, logger=quiet)
                log.info(f"✅ [GRVT] 클라이언트 초기화 (SubAcc: {self.sub_account_id})")
            except Exception as e:
                log.error(f"❌ [GRVT] SDK 초기화 실패: {e}")
                
        self.target_instruments = []
        self.reverse_map = {} 
        if settings:
            for ticker, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'grvt' in cfg['symbols']:
                    sym = cfg['symbols']['grvt']
                    if sym: self.target_instruments.append(sym); self.reverse_map[sym] = ticker 

    async def load_markets(self):
        if not self.grvt: return
        try:
            await self.grvt.initialize()
            if hasattr(self.grvt, 'markets'):
                for sym, m in self.grvt.markets.items():
                    base = sym.split('_')[0]
                    min_sz = m.get('min_size') or m.get('limits', {}).get('amount', {}).get('min', 0.001)
                    tick_size = m.get('tick_size') or 0.01
                    max_lev = m.get('limits', {}).get('leverage', {}).get('max', 20)
                    try: prec = int(round(-math.log10(float(min_sz)), 0))
                    except: prec = 3
                    self.market_info[base] = {
                        'qty_prec': prec, 'min_size': float(min_sz), 
                        'max_lev': float(max_lev), 'tick_size': float(tick_size)
                    }
                    
            try:
                path = get_grvt_endpoint(GrvtEnv.PROD, "GET_ALL_INITIAL_LEVERAGE")
                payload = {"sub_account_id": str(self.sub_account_id)}
                res = await self.grvt._auth_and_post(path, payload)
                if res and "results" in res:
                    for item in res["results"]:
                        instr = item.get("instrument")
                        if instr:
                            base = instr.split('_')[0]
                            real_max_lev = float(item.get("max_leverage", 20))
                            if base in self.market_info:
                                self.market_info[base]['max_lev'] = real_max_lev
                    log.info("✅ [GRVT] 레버리지 정보 동기화 완료")
            except: pass
            log.info(f"✅ [GRVT] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e: log.error(f"❌ [GRVT] 로드 중 에러: {e}")

    async def get_balance(self):
        if not self.grvt: return None
        try:
            bal = await self.grvt.fetch_balance()
            equity = float(bal.get('USDT', {}).get('total', 0))
            available = float(bal.get('USDT', {}).get('free', 0))
            
            raw_pos = await self.grvt.fetch_positions()
            positions = []
            for p in raw_pos:
                sz = float(p.get('size') or p.get('contracts') or 0)
                if sz != 0:
                    instr = p.get('instrument', 'Unknown')
                    sym = instr.split('_')[0] if '_' in instr else instr
                    positions.append({
                        'symbol': sym, 'size': abs(sz), 'amount': abs(sz),
                        'side': 'LONG' if sz > 0 else 'SHORT', 'entry_price': float(p.get('entry_price', 0))
                    })
            return {'equity': equity, 'available': available, 'positions': positions}
        except: return None

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        full_symbol = f"{symbol}_USDT_Perp"
        info = self.market_info.get(symbol, {})
        tick_size = info.get('tick_size', 0.01)
        
        current_price = 0.0
        try:
            try:
                ticker = await self.grvt.fetch_ticker(full_symbol)
                current_price = float(ticker.get('last') or ticker.get('close') or 0)
            except: pass
            if current_price == 0:
                try:
                    ob = await self.grvt.fetch_order_book(full_symbol, limit=1)
                    if side.upper() == 'BUY' and ob.get('asks'): current_price = float(ob['asks'][0][0])
                    elif side.upper() == 'SELL' and ob.get('bids'): current_price = float(ob['bids'][0][0])
                except: pass

            if current_price > 0:
                raw_limit = current_price * 1.05 if side.upper() == 'BUY' else current_price * 0.95
            elif price is not None and price > 0:
                raw_limit = price * 1.05 if side.upper() == 'BUY' else price * 0.95
            else:
                log.error(f"❌ [GRVT] 가격 정보 없음. 주문 취소.")
                return None
            
            limit_px = float(Decimal(str(raw_limit)).quantize(Decimal(str(tick_size)), rounding=ROUND_HALF_UP))
            order_type = 'limit'; log_msg = f"Limit IOC @ {limit_px} (Tick: {tick_size})"

            res = await self.grvt.create_order(
                full_symbol, order_type, side.lower(), val_amt, limit_px,
                {'reduce_only': reduce_only, 'time_in_force': 'IMMEDIATE_OR_CANCEL'}
            )
            if isinstance(res, dict) and (res.get('code') or res.get('error')):
                log.error(f"❌ [GRVT] 주문 거부: {res}")
                return None
            log.info(f"🚀 [GRVT] 주문 전송: {symbol} {side} {val_amt} ({log_msg})")
            return res
        except Exception as e:
            log.error(f"❌ [GRVT] 주문 에러: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        if not self.grvt: return False, leverage
        full_symbol = f"{symbol}_USDT_Perp"
        try:
            path = get_grvt_endpoint(GrvtEnv.PROD, "SET_INITIAL_LEVERAGE")
            payload = {"sub_account_id": str(self.sub_account_id), "instrument": full_symbol, "leverage": str(leverage)}
            res = await self.grvt._auth_and_post(path, payload)
            if res and str(res.get("success", "")).lower() == "true":
                log.info(f"✅ [GRVT] {symbol} 레버리지 x{leverage} 설정 성공")
                return True, leverage
            return False, leverage
        except Exception as e:
            log.error(f"❌ [GRVT] 설정 실패: {e}")
            return False, leverage

    async def start_ws(self, callback: Callable):
        if not self.grvt: return
        self.ws_running = True
        while self.ws_running:
            try:
                params = {'api_key': self.api_key, 'private_key': self.private_key, 'trading_account_id': self.sub_account_id}
                loop = asyncio.get_running_loop()
                quiet = logging.getLogger("quiet_grvt")
                quiet.setLevel(logging.CRITICAL)
                self.ws = GrvtCcxtWS(env=GrvtEnv.PROD, loop=loop, logger=quiet, parameters=params)
                await self.ws.initialize() 
                def make_cb(instr):
                    async def wrapped(msg):
                        try:
                            feed = msg.get("feed")
                            if feed:
                                b, a = feed.get('bids', []), feed.get('asks', [])
                                if b and a:
                                    bot_sym = self.reverse_map.get(instr, instr.split('_')[0])
                                    bid_p, ask_p = float(b[0]['price']), float(a[0]['price'])
                                    if bot_sym == 'RESOLV' and bid_p > 10: return
                                    bbo = self._validate_and_format('GRVT', bot_sym, bid_p, ask_p)
                                    if bbo: 
                                        self.bbo_cache[bot_sym] = bbo
                                        self._log_heartbeat('GRVT', bot_sym, bid_p)
                                        await callback(bbo)
                        except: pass
                    return wrapped
                
                subs = self.target_instruments
                if not subs and settings:
                    for ticker, cfg in settings.TARGET_PAIRS_CONFIG.items():
                         if 'grvt' in cfg['symbols']:
                             sym = cfg['symbols']['grvt']
                             if sym: subs.append(sym); self.reverse_map[sym] = ticker

                for instr in subs:
                    if instr: await self.ws.subscribe(stream='book.s', callback=make_cb(instr), params={'instrument': instr, 'depth': 10})
                while self.ws_running: await asyncio.sleep(1)
            except: await asyncio.sleep(5)
    
    async def close(self):
        try:
            if self.grvt and hasattr(self.grvt, '_session'):
                if not self.grvt._session.closed:
                    await self.grvt._session.close()
        except: pass

# ==========================================
# 4. Pacifica Implementation
# ==========================================
class PacificaExchange(Exchange):
    def __init__(self, main_address: str, agent_private_key: str):
        super().__init__()
        self.url = "https://api.pacifica.fi/api/v1"
        self.ws_url = "wss://ws.pacifica.fi/ws"
        self.main_addr = main_address
        self.agent_pk = agent_private_key
        
        if base58 and Keypair:
            try:
                self.kp = Keypair.from_base58_string(self.agent_pk)
                self.agent_pub = str(self.kp.pubkey())
            except Exception as e: log.error(f"❌ [PAC] 키 에러: {e}")

        self.target_mapping = {}
        self.virtual_spread = PAC_SPREAD
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'pacifica' in cfg['symbols']:
                    sym = cfg['symbols']['pacifica']
                    if sym:
                        self.target_mapping[sym.upper()] = t
                        if sym.startswith('k'): self.target_mapping[sym[1:].upper()] = t
                        if sym.startswith('1000'): self.target_mapping[sym.replace('1000', '').upper()] = t

    def _sign_and_build_body(self, type_str, payload):
        ts = int(time.time() * 1000)
        def sort_keys(o):
            if isinstance(o, dict): return {k: sort_keys(o[k]) for k in sorted(o.keys())}
            if isinstance(o, list): return [sort_keys(i) for i in o]
            return o
        msg_obj = {"timestamp": ts, "expiry_window": 5000, "type": type_str, "data": payload}
        sorted_msg = sort_keys(msg_obj)
        msg_str = json.dumps(sorted_msg, separators=(",", ":"))
        sig = base58.b58encode(bytes(self.kp.sign_message(msg_str.encode()))).decode()
        header = {"account": self.main_addr, "agent_wallet": self.agent_pub, "signature": sig, "timestamp": ts, "expiry_window": 5000}
        final_obj = {**header, **sort_keys(payload)}
        return json.dumps(final_obj, separators=(",", ":"))

    async def load_markets(self):
        try:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: requests.get(f"{self.url}/info"))
            if res.status_code == 200:
                for d in res.json().get('data', []):
                    sym = d['symbol']
                    lot = float(d.get('lot_size', 0.001))
                    prec = int(round(-math.log10(lot), 0)) if lot > 0 else 3
                    max_lev = float(d.get('max_leverage', 20))
                    self.market_info[sym] = {'qty_prec': prec, 'min_size': lot, 'max_lev': max_lev}
            log.info(f"✅ [PAC] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e: log.error(f"❌ [PAC] 로드 실패: {e}")

    async def get_balance(self):
        try:
            loop = asyncio.get_running_loop()
            r_acc = await loop.run_in_executor(None, lambda: requests.get(f"{self.url}/account", params={"account": self.main_addr}))
            equity = 0.0
            available = 0.0
            if r_acc.status_code == 200:
                d = r_acc.json().get('data', {})
                equity = float(d.get('account_equity') or d.get('available_to_spend') or 0)
                available = float(d.get('available_to_spend') or 0)

            r_pos = await loop.run_in_executor(None, lambda: requests.get(f"{self.url}/positions", params={"account": self.main_addr}))
            pos_list = []
            if r_pos.status_code == 200:
                for p in r_pos.json().get('data', []):
                    sz = float(p.get('amount') or p.get('position_size') or 0)
                    if sz != 0:
                        side_raw = p.get('side', '').lower()
                        side = 'LONG' if side_raw in ['bid', 'buy', 'long'] else 'SHORT'
                        pos_list.append({
                            'symbol': p.get('symbol'),
                            'size': abs(sz), 
                            'amount': abs(sz), 
                            'side': side,
                            'entry_price': float(p.get('entry_price', 0))
                        })
            return {'equity': equity, 'available': available, 'positions': pos_list}
        except: return None

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        prec = self.market_info.get(symbol, {}).get('qty_prec', 3)
        fmt_amount = f"{val_amt:.{prec}f}"
        payload = {
            "symbol": symbol, "side": "bid" if side.upper() == 'BUY' else "ask",
            "amount": fmt_amount, "reduce_only": reduce_only,
            "slippage_percent": "0.5", "client_order_id": str(uuid.uuid4())
        }
        body_str = self._sign_and_build_body("create_market_order", payload)
        try:
            loop = asyncio.get_running_loop()
            headers = {"Content-Type": "application/json"}
            res = await loop.run_in_executor(None, lambda: requests.post(f"{self.url}/orders/create_market", data=body_str, headers=headers))
            try: rj = res.json()
            except: rj = res.text
            if res.status_code == 200 and isinstance(rj, dict) and rj.get('success'):
                log.info(f"✅ [PAC] 주문 성공: {symbol} {side} {val_amt} (Reduce: {reduce_only})")
                return rj
            else:
                log.error(f"❌ [PAC] 주문 실패: {rj}")
                return None
        except Exception as e:
            log.error(f"❌ [PAC] 주문 예외: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        try:
            payload = {"symbol": symbol, "leverage": leverage, "margin_mode": "cross"}
            body_str = self._sign_and_build_body("update_leverage", payload)
            loop = asyncio.get_running_loop()
            headers = {"Content-Type": "application/json"}
            await loop.run_in_executor(None, lambda: requests.post(f"{self.url}/account/leverage", data=body_str, headers=headers))
            return True, leverage
        except: return False, leverage

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://pacifica.fi"}
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers, ping_interval=30) as ws:
                    await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        if data.get("channel") == "prices":
                            payload = data.get("data", [])
                            items = payload if isinstance(payload, list) else []
                            if isinstance(payload, dict): items = [payload]
                            for item in items:
                                ticker = self.target_mapping.get(item.get("symbol", "").upper())
                                if ticker:
                                    price = float(item.get("mark") or item.get("oracle") or 0)
                                    if price > 0:
                                        bbo = self._validate_and_format('pacifica', ticker, price*(1-self.virtual_spread), price*(1+self.virtual_spread), 10000, 10000)
                                        if bbo:
                                            self.bbo_cache[ticker] = bbo
                                            if ticker == 'BTC': self._log_heartbeat('Pacifica', ticker, price)
                                            await callback(bbo)
            except Exception as e:
                await asyncio.sleep(5)

# ==========================================
# 5. Extended Implementation (Final Fix)
# ==========================================
class ExtendedExchange(Exchange):
    def __init__(self, private_key, public_key, api_key, vault):
        super().__init__()
        self.keys = {'pk': private_key, 'pub': public_key, 'api': api_key, 'vault': int(vault or 100001)}
        self.client = None; self.info_client = None; self.ready = False
        try:
            import x10.perpetual.configuration as c
            from x10.perpetual.accounts import StarkPerpetualAccount
            from x10.perpetual.simple_client.simple_trading_client import BlockingTradingClient
            from x10.perpetual.trading_client.account_module import AccountModule
            from x10.perpetual.orders import OrderSide, TimeInForce
            from x10.perpetual.order_object import create_order_object
            self.C = c; self.SPA = StarkPerpetualAccount; self.BTC = BlockingTradingClient; self.AM = AccountModule
            self.OS = OrderSide; self.TIF = TimeInForce; self.create_order = create_order_object
            self.ready = True
        except: pass
        self.base_url = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1"
        self.targets = {}
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'extended' in cfg['symbols']:
                    sym = cfg['symbols']['extended']
                    if sym and sym != "None": self.targets[sym] = t

    async def load_markets(self):
        if not self.ready: return
        try:
            acc = self.SPA(vault=self.keys['vault'], private_key=self.keys['pk'], public_key=self.keys['pub'], api_key=self.keys['api'])
            self.client = await self.BTC.create(endpoint_config=self.C.MAINNET_CONFIG, account=acc)
            self.orders_module = getattr(self.client, '_BlockingTradingClient__orders_module', None)
            self.info_client = self.AM(endpoint_config=self.C.MAINNET_CONFIG, api_key=self.keys['api'])
            mkts = await self.client.get_markets()
            for n, m in mkts.items():
                step = float(m.trading_config.min_order_size) 
                prec = int(round(-math.log10(step), 0)) if step < 1 else 0
                self.market_info[n.split('-')[0]] = {'min_size': step, 'qty_prec': prec, 'max_lev': 20, 'full_name': n}
            log.info(f"✅ [EXT] {len(self.market_info)}개 심볼 로드 완료")
        except: log.error("❌ [EXT] 로드 실패")

    async def get_balance(self):
        if not self.info_client: return None
        try:
            b = await self.info_client.get_balance()
            p = await self.info_client.get_positions()
            eq = float(b.data.equity) if (b and b.data) else 0.0
            
            available = 0.0
            if b and b.data:
                if hasattr(b.data, 'availableForTrade'):
                    available = float(b.data.availableForTrade)
                elif hasattr(b.data, 'available_for_trade'):
                    available = float(b.data.available_for_trade)
                else:
                    available = float(getattr(b.data, 'free_collateral', getattr(b.data, 'collateral', 0)))

            pos_list = []
            if p and p.data:
                for x in p.data:
                    sz = float(x.size)
                    if sz != 0: 
                        side_str = x.side.name if hasattr(x.side, 'name') else str(x.side)
                        pos_list.append({'symbol': x.market.split('-')[0], 'size': abs(sz), 'amount': abs(sz), 'side': side_str, 'entry_price': float(x.open_price)})
            return {'equity': eq, 'available': available, 'positions': pos_list}
        except Exception as e: 
            log.error(f"❌ [EXT] 잔고 조회 실패: {e}")
            return None

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        if not self.client or not self.orders_module: return None
        info = self.market_info.get(symbol)
        m_name = info['full_name'] if info else f"{symbol}-USD"
        
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        
        try:
            mkts = await self.client.get_markets()
            market = mkts.get(m_name)
            if not market: return None
            side_enum = self.OS.BUY if side.upper() == 'BUY' else self.OS.SELL
            
            if price is None: price = 100000 if side.upper() == 'BUY' else 1000
            
            px = Decimal(str(price)); exec_px = px * Decimal("1.03") if side.upper() == 'BUY' else px * Decimal("0.97")
            exec_px = market.trading_config.round_price(exec_px)
            
            qty_dec = Decimal(str(val_amt))
            
            order_obj = self.create_order(
                account=self.client._BlockingTradingClient__account,
                market=market, amount_of_synthetic=qty_dec, price=exec_px, side=side_enum,
                post_only=False, reduce_only=reduce_only, time_in_force=self.TIF.IOC,
                starknet_domain=self.C.MAINNET_CONFIG.starknet_domain
            )
            await self.orders_module.place_order(order_obj)
            log.info(f"✅ [EXT] 주문 성공: {symbol} {side} {val_amt}")
            return {'id': order_obj.id, 'status': 'filled'}
        except Exception as e:
            log.error(f"❌ [EXT] 주문 실패: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        try: await self.info_client.update_leverage(f"{symbol}-USD", Decimal(str(leverage))); return True, leverage
        except: return False, leverage
    
    async def start_ws(self, callback: Callable):
        self.ws_running = True
        subs = self.targets
        if not subs and settings:
             for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'extended' in cfg['symbols']:
                    sym = cfg['symbols']['extended']
                    if sym and sym != "None": subs[sym] = t

        async def _run(symbol, ticker):
            url = f"{self.base_url}/orderbooks/{symbol}"
            ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
            while self.ws_running:
                try:
                    async with websockets.connect(url, ssl=ssl_ctx) as ws:
                        async for msg in ws:
                            if not self.ws_running: break
                            payload = json.loads(msg)
                            inner = payload.get('data', {})
                            bids = inner.get('b', []) or inner.get('bids', [])
                            asks = inner.get('a', []) or inner.get('asks', [])
                            if bids and asks:
                                bid_p = float(bids[0]['p'] if isinstance(bids[0], dict) else bids[0][0])
                                ask_p = float(asks[0]['p'] if isinstance(asks[0], dict) else asks[0][0])
                                bbo = self._validate_and_format('EXT', ticker, bid_p, ask_p)
                                if bbo:
                                    self.bbo_cache[ticker] = bbo
                                    self._log_heartbeat('EXT', ticker, bid_p)
                                    await callback(bbo)
                except: await asyncio.sleep(5)
        tasks = [asyncio.create_task(_run(s, t)) for s, t in subs.items()]
        if tasks: await asyncio.gather(*tasks)
        else:
             while self.ws_running: await asyncio.sleep(1)

# ==========================================
# 6. Lighter Exchange (V01_2 Style: API-First Discovery)
# ==========================================
class LighterExchange(Exchange):
    def __init__(self, api_key: str, public_key: str):
        super().__init__()
        self.api_key = api_key; self.public_key = public_key
        self.client = None; self.is_ready = False
        
        self.ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
        self.id_map = {} # ID -> Ticker
        self.ticker_map = {} # Ticker -> ID
        
        try:
            import lighter
            from lighter.configuration import Configuration
            self.lighter = lighter; self.Configuration = Configuration
            self.is_ready = True
        except: log.error("❌ [Lighter] SDK 미설치")

        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'lighter' in cfg['symbols']:
                    val = cfg['symbols']['lighter']
                    try:
                        if val is not None and isinstance(val, int): self.id_map[val] = t
                    except: pass

    async def load_markets(self):
        if not self.is_ready: return
        
        # [수정] V01_2 스타일: API에서 모든 마켓 정보를 가져와서 매핑 구축
        try:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: requests.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBooks", timeout=5))
            
            if res.status_code == 200:
                self.id_map.clear()
                self.ticker_map.clear()
                
                # 1. API 데이터로 맵 구축
                for item in res.json().get('order_books', []):
                    mid = int(item.get('market_id', 0))
                    full_sym = item.get('symbol', '')
                    ticker = full_sym.split('-')[0] # "ETH-USDC" -> "ETH"
                    
                    self.id_map[mid] = ticker
                    self.ticker_map[ticker] = mid
                    
                    self.market_info[ticker] = {
                        'qty_prec': int(item.get('supported_size_decimals', 3)),
                        'price_prec': int(item.get('supported_price_decimals', 2)),
                        'min_size': float(item.get('min_base_amount', '0.001')),
                        'market_id': mid,
                        'max_lev': 20
                    }
                log.info(f"✅ [LTR] API 자동 매핑 완료 ({len(self.id_map)}개 마켓)")
        except Exception as e:
            log.error(f"❌ [Lighter] 마켓 로드 실패: {e}")

        # 2. 클라이언트 초기화
        try:
            acc_idx = 288085
            pk = self.api_key[2:] if self.api_key.startswith("0x") else self.api_key
            sig = inspect.signature(self.lighter.SignerClient)
            init_kwargs = {
                "url": "https://mainnet.zklighter.elliot.ai",
                "account_index": acc_idx, "api_key_index": 2,
                "private_key": pk, "api_private_key": pk, "private_keys": {2: pk}, "api_private_keys": {2: pk}
            }
            valid_kwargs = {k: v for k, v in init_kwargs.items() if k in sig.parameters}
            self.client = self.lighter.SignerClient(**valid_kwargs)
            if not hasattr(self.client, 'api_key_index'): self.client.api_key_index = 2
            log.info(f"✅ [Lighter] 클라이언트 초기화 (Acc:{acc_idx})")
        except Exception as e: log.error(f"❌ [Lighter] 초기화 에러: {e}")

    async def get_balance(self):
        if not self.client: return None
        try:
            acc_api = self.lighter.AccountApi(self.client.api_client)
            idx = getattr(self.client, 'account_index', 288085)
            resp = await acc_api.account(by="index", value=str(idx))
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
                        pos_list.append({'symbol': getattr(p, 'symbol', ''), 'size': abs(sz), 'amount': abs(sz), 'side': side, 'entry_price': float(getattr(p, 'avg_entry_price', 0))})
            return {'equity': equity, 'available': available, 'positions': pos_list}
        except: return None

    async def set_leverage(self, symbol, leverage):
        if not self.client: return False, leverage
        mid = self.ticker_map.get(symbol)
        if mid is None: return False, leverage
        fallback_levels = sorted(list(set([leverage, 20, 10, 5, 3, 1])), reverse=True)
        fallback_levels = [l for l in fallback_levels if l <= leverage]
        for lev in fallback_levels:
            try:
                log.info(f"⚙️ [Lighter] {symbol} 레버리지 x{lev} 시도...")
                from decimal import Decimal
                _, _, err = await self.client.update_leverage(market_index=mid, margin_mode=0, leverage=Decimal(lev))
                if not err:
                    log.info(f"✅ [Lighter] {symbol} 레버리지 x{lev} 설정 성공")
                    return True, lev
            except: pass
        return False, leverage

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        if not self.client: return None
        mid = self.ticker_map.get(symbol)
        if not mid: return None
        info = self.market_info.get(symbol)
        if not info: return None
        base_amt = int(amount * (10 ** info['qty_prec']))
        target_price = 100000000 if side.upper() == 'BUY' else 0.01 
        exec_price = int(target_price * (10 ** info['price_prec'])) or 1
        try:
            _, hash, err = await self.client.create_market_order(
                market_index=mid, client_order_index=int(time.time()), 
                base_amount=base_amt, avg_execution_price=exec_price, is_ask=(side.upper()=='SELL'), reduce_only=reduce_only
            )
            if not err:
                log.info(f"✅ [LTR] 주문 성공: {symbol} {side}")
                return {'id': hash, 'status': 'open'}
            log.error(f"❌ [LTR] 에러: {err}")
            return None
        except: return None

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0"}
        log.info(f"[Lighter] {len(self.id_map)}개 구독")
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                    for mid in self.id_map.keys():
                        await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{mid}"}))
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        if data.get('type') == 'ping': await ws.send(json.dumps({"type": "pong"})); continue
                        if data.get('type') == 'update/order_book':
                            channel = data.get('channel', '')
                            try:
                                mid = int(channel.split(':')[1]) if ':' in channel else int(channel.split('/')[1])
                                if mid in self.id_map:
                                    ticker = self.id_map[mid]
                                    ob = data.get('order_book', {})
                                    bids, asks = ob.get('bids', []), ob.get('asks', [])
                                    if bids and asks:
                                        best_bid = float(bids[0]['price'])
                                        best_ask = float(asks[0]['price'])
                                        bid_s = float(bids[0]['size'])
                                        ask_s = float(asks[0]['size'])
                                        if ticker in ['BTC', 'ETH', 'BNB', 'SOL'] and best_bid < 1.0: continue
                                        bbo = self._validate_and_format('lighter', ticker, best_bid, best_ask, bid_s, ask_s)
                                        if bbo:
                                            self.bbo_cache[ticker] = bbo
                                            self._log_heartbeat('Lighter', ticker, best_bid)
                                            await callback(bbo)
                            except: pass
            except: await asyncio.sleep(5)

    # # [수정] V01_2 방식: start_ws 내에서 API 재호출하여 ID 매핑 확실히 함
    # async def start_ws(self, callback: Callable):
    #     self.ws_running = True
    #     headers = {"User-Agent": "Mozilla/5.0"}
        
    #     # 1. API로 마켓 정보 다시 로드 (ID 매핑 보장)
    #     await self.load_markets()
        
    #     subs = list(self.id_map.keys())
    #     log.info(f"📡 [Lighter] WS 시작 ({len(subs)}개 마켓 구독)")
        
    #     while self.ws_running:
    #         try:
    #             async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
    #                 # 일괄 구독 요청
    #                 for mid in subs:
    #                     await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{mid}"}))
                    
    #                 async for msg in ws:
    #                     if not self.ws_running: break
    #                     data = json.loads(msg)
                        
    #                     # Ping/Pong 처리
    #                     if data.get('type') == 'ping': 
    #                         await ws.send(json.dumps({"type": "pong"}))
    #                         continue
                            
    #                     # 데이터 수신
    #                     if data.get('type') == 'update/order_book':
    #                         try:
    #                             # channel format: "order_book/84"
    #                             part = data.get('channel', '').split('/')[-1]
    #                             mid = int(part)
                                
    #                             if mid in self.id_map:
    #                                 ticker = self.id_map[mid]
    #                                 ob = data.get('order_book', {})
    #                                 bids, asks = ob.get('bids', []), ob.get('asks', [])
                                    
    #                                 if bids and asks:
    #                                     bp, ap = float(bids[0]['price']), float(asks[0]['price'])
    #                                     # 유효성 검사
    #                                     if bp > 0 and ap > 0:
    #                                         bbo = self._validate_and_format('LTR', ticker, bp, ap)
    #                                         if bbo:
    #                                             self.bbo_cache[ticker] = bbo
    #                                             # 대표 코인만 하트비트
    #                                             if ticker == 'ETH': self._log_heartbeat('Lighter', ticker, bp)
    #                                             await callback(bbo)
    #                         except: pass
    #         except: await asyncio.sleep(5)

    async def close(self):
        self.ws_running = False
        try:
            if self.client and hasattr(self.client, 'api_client'):
                await self.client.api_client.close()
        except: pass