import asyncio
import logging
import json
import websockets
import ssl
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable
import sys
import time
import math
import os
from decimal import Decimal, ROUND_FLOOR
import requests
import uuid
import inspect # Lighter용


# --- [필수] Pacifica 및 공통 라이브러리 ---
try:
    import base58
    from solders.keypair import Keypair
except ImportError:
    base58 = None
    Keypair = None

# --- Hyperliquid SDK ---
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange as HLExchange
    from hyperliquid.utils import constants as hl_constants
    from hyperliquid.utils.types import Cloid
    from eth_account import Account
except ImportError:
    Info = None; HLExchange = None; Cloid = None; Account = None

# --- GRVT SDK ---
try:
    from pysdk.grvt_ccxt_ws import GrvtCcxtWS
    from pysdk.grvt_ccxt_env import GrvtEnv
except ImportError:
    GrvtCcxtWS = None; GrvtEnv = None

# --- Settings & Constants ---
try:
    import settings
    # 설정 파일에서 가져오거나 기본값 사용
    PAC_SPREAD = getattr(settings, 'PACIFICA_VIRTUAL_SPREAD', 0.0005)
except ImportError:
    settings = None
    PAC_SPREAD = 0.0005 

# --- Logging ---
logging.getLogger("pysdk").setLevel(logging.ERROR) 
logging.getLogger("GrvtCcxtWS").setLevel(logging.ERROR)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger("ExchangeAPIs")
log.setLevel(logging.INFO)

# --- Based App Constants ---
BASED_BUILDER_ADDRESS = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
BASED_BUILDER_FEE = 25
BASED_CLOID_STR = "0xba5ed11067f2cc08ba5ed10000ba5ed1"

class Exchange(ABC):
    def __init__(self):
        self.ws_running = False
        self.bbo_cache = {} 
        self.last_log_time = 0
        self.last_prices = {} 
        self.market_info = {} # {Ticker: {'qty_prec': 3, 'min_size': 0.001}, ...}

    @abstractmethod
    async def start_ws(self, callback: Callable):
        pass

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
        
        if last_price:
            if abs(current_mid - last_price) / last_price > 0.05: return None
        
        self.last_prices[symbol] = current_mid
        return {
            'symbol': symbol, 'bid': bid, 'ask': ask,
            'bid_qty': bid_qty, 'ask_qty': ask_qty,
            'exchange': exchange, 'timestamp': time.time()
        }
    
    async def set_leverage(self, symbol: str, leverage: int):
        pass

        

    @abstractmethod
    async def load_markets(self):
        pass

    # [수정] reduce_only 파라미터 추가
    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, amount: float, price: float = None, reduce_only: bool = False): pass

    def validate_amount(self, symbol: str, amount: float) -> float:
        # 심볼 보정
        base = symbol.split('_')[0].split('-')[0]
        if base.startswith('k'): base = base[1:]
        if base.startswith('1000'): base = base[4:]
        
        info = self.market_info.get(base)
        if not info: return round(amount, 4)

        prec = info.get('qty_prec', 3)
        min_sz = info.get('min_size', 0.0)

        if amount < min_sz:
            log.warning(f"⚠️ [{base}] 주문량({amount}) < 최소({min_sz}) -> 주문 스킵")
            return 0.0

        # 내림 처리 (Floor)
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
        
        if Info and self.private_key:
            try:
                # Agent Account 로드
                account = Account.from_key(self.private_key)
                self.agent_address = account.address
                
                # Main Address가 없으면 Agent Address를 Main으로 간주 (Fallback)
                if not self.main_address:
                    self.main_address = self.agent_address
                    
                self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True)
                self.exchange = HLExchange(account, hl_constants.MAINNET_API_URL)
                
                log.info(f"✅ [HL] 초기화 (Vault: {self.main_address[:6]}..)")
            except Exception as e:
                log.error(f"❌ [HL] 초기화 실패: {e}")

    async def load_markets(self):
        try:
            meta = self.info.meta()
            for asset in meta['universe']:
                name = asset['name']
                self.market_info[name] = {
                    'qty_prec': asset['szDecimals'],
                    'min_size': 10 ** (-asset['szDecimals']),
                    'max_lev': asset['maxLeverage']
                }
            log.info(f"✅ [HL] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e: log.error(f"❌ [HL] 로드 실패: {e}")

    async def get_balance(self):
        try:
            # [수정] self.vault_address -> self.main_address
            # API 호출: user_state(main_address)
            state = self.info.user_state(self.main_address)
            
            margin = state.get('marginSummary', {})
            equity = float(margin.get('accountValue', 0))
            
            # 포지션 파싱
            raw_positions = state.get('assetPositions', [])
            positions = []
            for p in raw_positions:
                pos_data = p.get('position', {})
                coin = pos_data.get('coin', '')
                size = float(pos_data.get('szi', 0))
                if size != 0:
                    positions.append({
                        'symbol': coin,
                        'size': abs(size),
                        'amount': abs(size),
                        'side': 'LONG' if size > 0 else 'SHORT',
                        'entry_price': float(pos_data.get('entryPx', 0))
                    })

            return {'equity': equity, 'positions': positions}
        except Exception as e:
            log.error(f"❌ [HL] 잔고 조회 실패: {e}")
            return None

    # [수정] reduce_only 파라미터 적용
    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        
        is_buy = (side.upper() == 'BUY')
        if price is None:
            price = float(self.info.all_mids().get(symbol, 0))
        
        limit_px = price * 1.05 if is_buy else price * 0.95
        limit_px = float(f"{limit_px:.5g}")

        order = {
            "coin": symbol, "is_buy": is_buy, "sz": val_amt, "limit_px": limit_px,
            "order_type": {"limit": {"tif": "Ioc"}}, 
            "reduce_only": reduce_only, # 여기 적용됨
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
            return True
        except: return False

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
                                        if price > 0:
                                            bbo = self._validate_and_format('hyperliquid', bot_symbol, price*0.9995, price*1.0005)
                                            if bbo:
                                                self.bbo_cache[bot_symbol] = bbo
                                                if bot_symbol == 'BTC': self._log_heartbeat('HL', bot_symbol, price)
                                                await callback(bbo)
                                    except: pass
            except: await asyncio.sleep(5)

# ==========================================
# 3. GRVT Implementation (업데이트됨)
# ==========================================
class GrvtExchange(Exchange):
    def __init__(self):
        super().__init__()
        self.grvt = None
        
        if GrvtCcxtWS:
            try:
                loop = asyncio.get_running_loop()
            except: 
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            api_key = os.getenv('GRVT_API_KEY')
            private_key = os.getenv('GRVT_PRIVATE_KEY') or os.getenv('GRVT_SECRET_KEY')
            sub_account_id = os.getenv('GRVT_TRADING_ACCOUNT_ID')

            if not private_key:
                log.error("❌ [GRVT] Private Key가 없습니다.")
            
            params = {
                'api_key': api_key, 
                'private_key': private_key,
                'trading_account_id': sub_account_id
            }
            
            try:
                self.grvt = GrvtCcxtWS(env=GrvtEnv.PROD, loop=loop, parameters=params)
                log.info(f"✅ [GRVT] 클라이언트 초기화 (SubAcc: {sub_account_id})")
            except Exception as e:
                log.error(f"❌ [GRVT] SDK 초기화 실패: {e}")

    async def load_markets(self):
        if not self.grvt: return
        try:
            await self.grvt.initialize()
            if hasattr(self.grvt, 'markets') and self.grvt.markets:
                for sym, m in self.grvt.markets.items():
                    base = sym.split('_')[0]
                    min_sz = m.get('min_size')
                    if min_sz is None: 
                        min_sz = m.get('limits', {}).get('amount', {}).get('min', 0.001)
                    try: prec = int(round(-math.log10(float(min_sz)), 0))
                    except: prec = 3
                    self.market_info[base] = {'qty_prec': prec, 'min_size': float(min_sz)}
                log.info(f"✅ [GRVT] {len(self.market_info)}개 심볼 로드 완료")
            else:
                log.warning("⚠️ [GRVT] 마켓 데이터 없음")
        except Exception as e:
            log.error(f"❌ [GRVT] 로드 중 에러: {e}")

    async def get_balance(self):
        if not self.grvt: return None
        try:
            bal = await self.grvt.fetch_balance()
            equity = float(bal.get('USDT', {}).get('total', 0))
            
            raw_positions = await self.grvt.fetch_positions()
            positions = []
            for p in raw_positions:
                size = float(p.get('size') or p.get('contracts') or p.get('amount') or 0)
                if size != 0:
                    positions.append({
                        'symbol': p.get('symbol', '').split('_')[0], 
                        'size': abs(size), 
                        'amount': abs(size), 
                        'side': 'LONG' if size > 0 else 'SHORT', 
                        'entry_price': float(p.get('entry_price', 0))
                    })
            return {'equity': equity, 'positions': positions}
        except Exception as e:
            log.error(f"❌ [GRVT] 잔고 조회 실패: {e}") 
            return None

    # [핵심 수정] Hybrid 주문 시스템
    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        
        full_symbol = f"{symbol}_USDT_Perp"
        current_price = 0.0
        use_market_order = False  # 시장가 주문 사용 여부

        try:
            # 1. 가격 조회 시도
            try:
                ticker = await self.grvt.fetch_ticker(full_symbol)
                current_price = float(ticker.get('last') or ticker.get('close') or 0)
            except: pass

            # 2. 가격 조회 실패 시 호가창 조회 (안전한 .get 사용)
            if current_price == 0:
                try:
                    ob = await self.grvt.fetch_order_book(full_symbol, limit=1)
                    # .get()을 사용하여 KeyError 방지
                    asks = ob.get('asks', [])
                    bids = ob.get('bids', [])
                    
                    if side.upper() == 'BUY' and asks:
                        current_price = float(asks[0][0])
                    elif side.upper() == 'SELL' and bids:
                        current_price = float(bids[0][0])
                except Exception as e:
                    log.warning(f"⚠️ [GRVT] 호가창 조회 실패: {e}")

            # 3. [전략 결정] 가격을 알면 'Limit IOC', 모르면 'True Market'
            if current_price > 0:
                # 가격을 아는 경우: 안전하게 Limit IOC 사용 (슬리피지 1%)
                if side.upper() == 'BUY':
                    limit_px = current_price * 1.01
                else:
                    limit_px = current_price * 0.99
                
                order_type = 'limit'
                log_msg = f"Limit IOC @ {limit_px:.2f}"
            else:
                # 가격을 모르는 경우: V01_2처럼 'Market' 주문 사용 (무조건 체결)
                use_market_order = True
                order_type = 'market'
                limit_px = None # 시장가는 가격 불필요
                log_msg = "Market Order (Fallback)"
                log.warning(f"⚠️ [GRVT] 가격 정보 없음 -> {log_msg} 전환")

            # 4. 파라미터 구성
            # GRVT SDK는 Market 주문일 때 limit_price를 무시하거나 None이어야 함
            tif_val = 'IMMEDIATE_OR_CANCEL'
            params = {
                'reduce_only': reduce_only,
                'time_in_force': tif_val
            }
            
            # 5. 주문 전송
            res = await self.grvt.create_order(
                full_symbol, 
                order_type,          
                side.lower(), 
                val_amt, 
                limit_px,         
                params
            )
            
            # 6. 결과 확인
            if isinstance(res, dict) and (res.get('code') or res.get('error')):
                log.error(f"❌ [GRVT] 주문 거부: {res}")
                return None
            
            log.info(f"🚀 [GRVT] 주문 전송 완료: {symbol} {side} {val_amt} ({log_msg})")
            return res

        except Exception as e:
            log.error(f"❌ [GRVT] 주문 에러: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        try:
            if hasattr(self.grvt, 'set_leverage'):
                await self.grvt.set_leverage(leverage, f"{symbol}_USDT_Perp")
                return True
        except: pass
        return False
    
    async def start_ws(self, cb): pass
    
    async def close(self):
        if self.grvt and hasattr(self.grvt, '_session') and self.grvt._session:
            if not self.grvt._session.closed:
                await self.grvt._session.close()



# ==========================================
# 4. Pacifica Implementation (자동화 업데이트)
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
            except Exception as e:
                log.error(f"❌ [PAC] 키 에러: {e}")

        self.target_mapping = {}
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'pacifica' in cfg['symbols']:
                    s = cfg['symbols']['pacifica']
                    if s: 
                        self.target_mapping[s.upper()] = t
                        if s.startswith('k'): self.target_mapping[s[1:].upper()] = t

    def _sign_and_build_body(self, type_str, payload):
        ts = int(time.time() * 1000)
        
        # 1. 정렬 함수
        def sort_keys(o):
            if isinstance(o, dict): 
                return {k: sort_keys(o[k]) for k in sorted(o.keys())}
            if isinstance(o, list): 
                return [sort_keys(i) for i in o]
            return o
            
        # 2. 전체 메시지 구조 생성 (이 상태에서 정렬해야 함)
        msg_obj = {
            "timestamp": ts, 
            "expiry_window": 5000, 
            "type": type_str, 
            "data": payload
        }
        
        # [핵심 수정] 전체 메시지를 정렬 (헤더 포함)
        sorted_msg_obj = sort_keys(msg_obj)
        msg_str = json.dumps(sorted_msg_obj, separators=(",", ":"))
        
        sig = base58.b58encode(bytes(self.kp.sign_message(msg_str.encode()))).decode()
        
        header = {
            "account": self.main_addr, 
            "agent_wallet": self.agent_pub, 
            "signature": sig, 
            "timestamp": ts, 
            "expiry_window": 5000
        }
        
        # 3. Payload도 정렬해서 Body 생성
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
                    self.market_info[sym] = {'qty_prec': prec, 'min_size': lot, 'max_lev': d.get('max_leverage')}
            log.info(f"✅ [PAC] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e: log.error(f"❌ [PAC] 로드 실패: {e}")

    async def get_balance(self):
        try:
            loop = asyncio.get_running_loop()
            r_acc = await loop.run_in_executor(None, lambda: requests.get(f"{self.url}/account", params={"account": self.main_addr}))
            equity = 0.0
            if r_acc.status_code == 200:
                d = r_acc.json().get('data', {})
                equity = float(d.get('account_equity') or d.get('available_to_spend') or 0)

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
            return {'equity': equity, 'positions': pos_list}
        except: return None

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        val_amt = self.validate_amount(symbol, amount)
        if val_amt <= 0: return None
        
        prec = self.market_info.get(symbol, {}).get('qty_prec', 3)
        fmt_amount = f"{val_amt:.{prec}f}"
        
        payload = {
            "symbol": symbol, 
            "side": "bid" if side.upper() == 'BUY' else "ask",
            "amount": fmt_amount, 
            "reduce_only": reduce_only,
            "slippage_percent": "0.5", 
            "client_order_id": str(uuid.uuid4())
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
            return True
        except: return False

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://pacifica.fi"}
        log.info(f"[Pacifica] WS 연결 시도...")
        
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers, ping_interval=None) as ws:
                    await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
                    log.info("[Pacifica] 가격 스트림 구독 완료")
                    
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        
                        if data.get("channel") == "prices":
                            payload = data.get("data", [])
                            items = payload if isinstance(payload, list) else [payload]
                            
                            for item in items:
                                raw_sym = item.get("symbol", "").upper()
                                # 매핑된 티커 찾기
                                ticker = self.target_mapping.get(raw_sym)
                                
                                if ticker:
                                    price = float(item.get("mark") or item.get("oracle") or 0)
                                    if price > 0:
                                        bbo = self._validate_and_format(
                                            'pacifica', ticker, 
                                            price * (1 - self.virtual_spread), 
                                            price * (1 + self.virtual_spread)
                                        )
                                        if bbo:
                                            self.bbo_cache[ticker] = bbo
                                            await callback(bbo)
            except Exception as e:
                log.warning(f"[Pacifica] WS 연결 끊김: {e}. 5초 후 재연결...")
                await asyncio.sleep(5)

# 5. Extended, 6. Lighter (생략 - 기존 유지)
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
            from x10.perpetual.order_object import create_order_object # [추가]
            
            self.C = c; self.SPA = StarkPerpetualAccount; self.BTC = BlockingTradingClient; self.AM = AccountModule
            self.OS = OrderSide; self.TIF = TimeInForce; self.create_order = create_order_object
            self.ready = True
        except: log.error("❌ [EXT] SDK 미설치")

    async def load_markets(self):
        if not self.ready: return
        try:
            acc = self.SPA(vault=self.keys['vault'], private_key=self.keys['pk'], public_key=self.keys['pub'], api_key=self.keys['api'])
            self.client = await self.BTC.create(endpoint_config=self.C.MAINNET_CONFIG, account=acc)
            
            # [추가] 주문 모듈 직접 접근
            self.orders_module = getattr(self.client, '_BlockingTradingClient__orders_module', None)
            
            self.info_client = self.AM(endpoint_config=self.C.MAINNET_CONFIG, api_key=self.keys['api'])
            
            mkts = await self.client.get_markets()
            for n, m in mkts.items():
                self.market_info[n.split('-')[0]] = {'min_size': float(m.trading_config.min_order_size), 'qty_prec': 3, 'full': n}
            log.info(f"✅ [EXT] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e: log.error(f"❌ [EXT] 로드 실패: {e}")

    async def get_balance(self):
        if not self.info_client: return None
        try:
            b = await self.info_client.get_balance()
            p = await self.info_client.get_positions()
            eq = float(b.data.equity) if b.data else 0.0
            pos_list = []
            if p.data:
                for x in p.data:
                    sz = float(x.size)
                    if sz != 0: 
                        side_str = x.side.name if hasattr(x.side, 'name') else str(x.side)
                        pos_list.append({'symbol': x.market.split('-')[0], 'size': abs(sz), 'amount': abs(sz), 'side': side_str, 'entry_price': float(x.open_price)})
            return {'equity': eq, 'positions': pos_list}
        except: return None

    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        if not self.client or not self.orders_module: return None
        
        # 마켓 정보 확인
        info = self.market_info.get(symbol)
        m_name = info['full'] if info else f"{symbol}-USD"
        
        try:
            # 1. Market 객체
            mkts = await self.client.get_markets()
            market = mkts.get(m_name)
            if not market: return None

            side_enum = self.OS.BUY if side.upper() == 'BUY' else self.OS.SELL
            
            # 가격 산정 (슬리피지 3%)
            if price is None: price = 100000 if side.upper() == 'BUY' else 1000
            slip = Decimal("0.03")
            px = Decimal(str(price))
            exec_px = px * (1 + slip) if side.upper() == 'BUY' else px * (1 - slip)
            exec_px = market.trading_config.round_price(exec_px)
            qty_dec = Decimal(str(amount))

            # 2. 주문 객체 생성 (starknet_domain 추가)
            # create_order_object는 reduce_only 지원
            order_obj = self.create_order(
                account=self.client._BlockingTradingClient__account, # 내부 계정 객체 사용
                market=market,
                amount_of_synthetic=qty_dec,
                price=exec_px,
                side=side_enum,
                post_only=False,
                reduce_only=reduce_only,
                time_in_force=self.TIF.IOC,
                # [핵심] 누락되었던 인자 추가
                starknet_domain=self.C.MAINNET_CONFIG.starknet_domain
            )
            
            # 3. 주문 전송
            await self.orders_module.place_order(order_obj)
            
            log.info(f"✅ [EXT] 주문 성공: {symbol} {side} (Reduce: {reduce_only})")
            return {'id': order_obj.id, 'status': 'filled'}
            
        except Exception as e:
            log.error(f"❌ [EXT] 주문 실패: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        try: await self.info_client.update_leverage(f"{symbol}-USD", Decimal(str(leverage))); return True
        except: return False
    
    async def _maintain_socket(self, symbol: str, ticker: str, callback: Callable):
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
                            bid_s = float(bids[0]['q'] if isinstance(bids[0], dict) else bids[0][1])
                            ask_s = float(asks[0]['q'] if isinstance(asks[0], dict) else asks[0][1])
                            bbo = self._validate_and_format('extended', ticker, bid_p, ask_p, bid_s, ask_s)
                            if bbo:
                                self.bbo_cache[ticker] = bbo
                                await callback(bbo)
            except: await asyncio.sleep(5)

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        tasks = [asyncio.create_task(self._maintain_socket(s, t, callback)) for s, t in self.targets.items()]
        log.info(f"[Extended] {len(tasks)}개 연결")
        await asyncio.gather(*tasks)

# ==========================================
# 6. Lighter Exchange (SDK 활용 + 주문 기능 완비)
# ==========================================
class LighterExchange(Exchange):
    def __init__(self, api_key: str, public_key: str):
        super().__init__()
        self.api_key = api_key       # L2 Private Key
        self.public_key = public_key # L1 Wallet Address
        self.client = None           # SignerClient
        self.api_client = None       # ApiClient
        
        self.symbol_map = {}         # Symbol -> Market ID
        self.id_to_symbol = {}       # Market ID -> Symbol
        self.id_map = {}             # WS 호환용
        self.is_ready = False
        
        try:
            import lighter
            from lighter.configuration import Configuration
            self.lighter = lighter
            self.Configuration = Configuration
            self.is_ready = True
        except ImportError:
            log.error("❌ [Lighter] SDK 미설치")

        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'lighter' in cfg['symbols']:
                    val = cfg['symbols']['lighter']
                    try:
                        if val is not None and isinstance(val, int): 
                            self.id_map[val] = t
                            self.id_to_symbol[val] = t
                    except: pass

    async def load_markets(self):
        if not self.is_ready: return
        log.info("⏳ [Lighter] 마켓 정보 및 계정 로딩 중...")
        
        # 1. 마켓 정보 가져오기
        url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=5))
            
            if response.status_code == 200:
                data = response.json()
                order_books = data.get('order_books', [])
                count = 0
                for item in order_books:
                    symbol = item.get('symbol', '').upper()
                    market_id = int(item.get('market_id', 0))
                    
                    min_size = float(item.get('min_base_amount', '0.001'))
                    qty_prec = int(item.get('supported_size_decimals', 3))
                    price_prec = int(item.get('supported_price_decimals', 2))
                    
                    self.market_info[symbol] = {
                        'qty_prec': qty_prec,
                        'price_prec': price_prec,
                        'min_size': min_size,
                        'market_id': market_id
                    }
                    self.symbol_map[symbol] = market_id
                    self.id_to_symbol[market_id] = symbol
                    self.id_map[market_id] = symbol 
                    count += 1
                log.info(f"✅ [Lighter] {count}개 심볼 정보 로드 완료")
            else:
                log.error(f"❌ [Lighter] 정보 조회 실패: {response.status_code}")
                return
        except Exception as e:
            log.error(f"❌ [Lighter] 마켓 로드 중 에러: {e}")
            return

        # 2. 클라이언트 초기화 (스마트 로직)
        try:
            # 임시 클라이언트로 계정 인덱스 조회
            config = self.Configuration(host="https://mainnet.zklighter.elliot.ai")
            temp_client = self.lighter.ApiClient(configuration=config)
            account_api = self.lighter.AccountApi(temp_client)
            
            # 계정 탐색 (사용자님이 확인하신 288085 우선 사용)
            account_index = 288085 
            
            # (혹시 몰라 자동 탐색도 시도)
            try:
                acc_response = await account_api.accounts_by_l1_address(self.public_key)
                accounts_list = []
                if hasattr(acc_response, 'sub_accounts'): accounts_list = acc_response.sub_accounts
                elif isinstance(acc_response, dict): accounts_list = acc_response.get('sub_accounts', [])
                elif isinstance(acc_response, list): accounts_list = acc_response

                if accounts_list:
                    first_acc = accounts_list[0]
                    if hasattr(first_acc, 'index'): account_index = first_acc.index
                    elif isinstance(first_acc, dict): account_index = first_acc.get('index')
            except: pass # 실패 시 기본값(288085) 사용

            # [핵심] SignerClient 생성 (인자 필터링)
            api_idx = 2
            pk = self.api_key
            if pk.startswith("0x"): pk = pk[2:]

            # SDK 생성자 시그니처 확인
            sig = inspect.signature(self.lighter.SignerClient)
            params = sig.parameters
            
            # 가능한 모든 인자 후보군 정의
            candidates = {
                "url": "https://mainnet.zklighter.elliot.ai",
                "account_index": account_index,
                "api_key_index": api_idx,
                "private_key": pk,
                "api_private_key": pk,
                "private_keys": {api_idx: pk},
                "api_private_keys": {api_idx: pk}
            }

            # 실제 SDK가 요구하는 인자만 골라내기 (필터링)
            init_kwargs = {}
            for name in params:
                if name in candidates:
                    init_kwargs[name] = candidates[name]
            
            log.info(f"👉 [Lighter] 적용된 인자: {list(init_kwargs.keys())}")

            self.client = self.lighter.SignerClient(**init_kwargs)
            self.api_client = self.client.api_client
            
            # API Key Index 수동 주입 (SDK 내부 버그 방지용)
            if not hasattr(self.client, 'api_key_index'):
                self.client.api_key_index = api_idx

            log.info(f"✅ [Lighter] 클라이언트 초기화 완료 (Acc:{account_index})")
            
        except Exception as e:
            log.error(f"❌ [Lighter] 초기화 실패: {e}")

    # [수정] reduce_only 적용
    async def place_market_order(self, symbol, side, amount, price=None, reduce_only=False):
        if not self.client: return None
        info = self.market_info.get(symbol)
        if not info: return None
        
        base = int(amount * (10 ** info['qty_prec']))
        # Lighter는 가격 0 허용 안 함
        px = 100000000 if side.upper() == 'BUY' else 0.01 
        exec_px = int(px * (10 ** info['price_prec']))
        if exec_px <= 0: exec_px = 1

        try:
            tx, hash, err = await self.client.create_market_order(
                market_index=info['market_id'], client_order_index=int(time.time()), 
                base_amount=base, avg_execution_price=exec_px, is_ask=(side.upper()=='SELL'),
                reduce_only=reduce_only # 여기 적용
            )
            if not err:
                log.info(f"✅ [LTR] 주문 성공: {symbol} {side} (Reduce: {reduce_only})")
                return {'id': hash, 'status': 'open'}
            log.error(f"❌ [LTR] 주문 에러: {err}")
            return None
        except Exception as e:
            log.error(f"❌ [LTR] 주문 예외: {e}")
            return None

    async def set_leverage(self, symbol, leverage):
        try:
            if not self.client: return False
            market_id = self.symbol_map.get(symbol)
            if market_id is None: return False
            
            log.info(f"⚙️ [Lighter] {symbol} 레버리지 x{leverage} 설정...")
            _, _, err = await self.client.update_leverage(
                market_index=market_id,
                margin_mode=0, # Cross
                leverage=leverage
            )
            if err:
                log.error(f"❌ [Lighter] 설정 실패: {err}")
                return False
            log.info("✅ [Lighter] 레버리지 설정 성공")
            return True
        except: return False

    async def get_balance(self):
        try:
            if not self.client: return None
            account_api = self.lighter.AccountApi(self.api_client)
            acc_idx = getattr(self.client, 'account_index', 288085)
            
            resp = await account_api.account(by="index", value=str(acc_idx))
            
            # 응답 처리 (리스트 or 객체)
            if isinstance(resp, list) and resp: acc_data = resp[0]
            elif hasattr(resp, 'accounts') and resp.accounts: acc_data = resp.accounts[0]
            else: acc_data = resp

            equity = float(getattr(acc_data, 'collateral', 0))
            positions = []
            
            if hasattr(acc_data, 'positions'):
                for pos in acc_data.positions:
                    size = float(getattr(pos, 'position', 0))
                    if size != 0:
                        side = "LONG" if getattr(pos, 'sign', 0) == 1 else "SHORT"
                        positions.append({
                            'symbol': getattr(pos, 'symbol', 'Unknown'),
                            'amount': size,
                            'size': size,
                            'side': side,
                            'entry_price': float(getattr(pos, 'avg_entry_price', 0))
                        })
            return {'equity': equity, 'positions': positions}
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