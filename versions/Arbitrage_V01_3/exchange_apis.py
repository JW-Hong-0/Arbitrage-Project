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
from decimal import Decimal, ROUND_DOWN


# --- [추가] Pacifica 및 공통 라이브러리 ---
import requests
import uuid
try:
    import base58
    from solders.keypair import Keypair
except ImportError:
    base58 = None
    Keypair = None

# --- Hyperliquid SDK Imports ---
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange as HLExchange
    from hyperliquid.utils import constants as hl_constants
    from hyperliquid.utils.types import Cloid
    from eth_account import Account
except ImportError:
    Info = None; HLExchange = None; Cloid = None; Account = None

# --- GRVT SDK Imports ---
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
logging.getLogger("GrvtCcxtWS").setLevel(logging.CRITICAL)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger("ExchangeAPIs")
log.setLevel(logging.CRITICAL)

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
        self.market_info = {} 

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

    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, amount: float, price: float = None):
        pass

    def validate_amount(self, symbol: str, amount: float) -> float:
        """수량 자릿수 절삭 (내림)"""
        base_symbol = symbol.split('_')[0].split('-')[0].split('/')[0]
        if base_symbol not in self.market_info:
            return round(amount, 4)

        info = self.market_info[base_symbol]
        precision = info['qty_prec']
        min_size = info['min_size']

        # 최소 수량 미만이면 0 반환 (주문 방지)
        if amount < min_size:
            log.warning(f"⚠️ [{base_symbol}] 주문 수량({amount}) < 최소({min_size})")
            return 0.0

        factor = 10 ** precision
        return math.floor(amount * factor) / factor

# ==========================================
# 2. Hyperliquid Implementation
# ==========================================
class HyperliquidExchange(Exchange):
    def __init__(self, private_key=None):
        super().__init__()
        
        if not Info:
            log.error("❌ Hyperliquid SDK 미설치")
            return

        self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True)
        self.hl_exchange = None
        self.account_address = None
        self.meta = None  # <-- [추가] meta 속성 초기화
        
        if private_key:
            account = Account.from_key(private_key)
            self.hl_exchange = HLExchange(account, hl_constants.MAINNET_API_URL)
            
            # [핵심 수정] Agent 모드 지원을 위한 주소 분리
            self.agent_address = account.address  # 서명용 (Private Key의 주인)
            self.main_address = os.getenv("HYPERLIQUID_MAIN_ADDRESS") # 조회용 (자금이 있는 본체)

            if self.main_address:
                # 메인 주소가 있으면 그걸 조회용 주소로 설정
                self.account_address = self.main_address
                log.info(f"✅ [HL] 계정 연결 (Agent: {self.agent_address[:6]}.. -> Vault: {self.account_address[:6]}..)")
            else:
                # 없으면 에이전트 주소 사용 (일반 지갑일 경우)
                self.account_address = self.agent_address
                log.warning("⚠️ [HL] 메인 주소(HYPERLIQUID_MAIN_ADDRESS) 미설정! 잔고가 0으로 보일 수 있습니다.")

    async def load_markets(self):
        log.info("⏳ [HL] 시장 정보 로딩...")
        try:
            # [수정] 로컬 변수 meta 대신 self.meta에 저장하여 외부(TradeSizer)에서 접근 가능하게 함
            self.meta = self.info.meta() #
            for asset in self.meta['universe']:
                name = asset['name']
                sz_decimals = asset['szDecimals']
                self.market_info[name] = {
                    'qty_prec': sz_decimals,
                    'min_size': 10 ** (-sz_decimals)
                }
            log.info(f"✅ [HL] {len(self.market_info)}개 심볼 로드 완료")
        except Exception as e:
            log.error(f"❌ [HL] 로드 실패: {e}")

    def _round_to_sig_figs(self, num, sig_figs=5):
        if num == 0: return 0.0
        try:
            magnitude = int(math.floor(math.log10(abs(num))))
            digits = sig_figs - magnitude - 1
            return round(num, digits)
        except Exception:
            return num

    async def place_market_order(self, symbol: str, side: str, amount: float, price: float = None):
        if not self.hl_exchange: return None

        validated_amount = self.validate_amount(symbol, amount)
        if validated_amount <= 0: return None

        safe_price = price
        if safe_price is None:
            try:
                all_mids = self.info.all_mids()
                mid_price = float(all_mids.get(symbol, 0))
                if mid_price == 0: raise Exception("Price 0")
                slippage = 0.05
                if side.upper() == 'BUY':
                    safe_price = mid_price * (1 + slippage)
                else:
                    safe_price = mid_price * (1 - slippage)
            except Exception as e:
                log.error(f"❌ [HL] 가격 조회 실패: {e}")
                return None

        final_price = self._round_to_sig_figs(safe_price)
        is_buy = (side.upper() == 'BUY')
        cloid = Cloid.from_str(BASED_CLOID_STR)

        order_request = {
            "coin": symbol,
            "is_buy": is_buy,
            "sz": validated_amount,
            "limit_px": final_price,
            "order_type": {"limit": {"tif": "Ioc"}},
            "reduce_only": False,
            "cloid": cloid 
        }

        log.info(f"🚀 [HL Order] {side} {symbol} {validated_amount} @ {final_price} (Builder: BasedApp)")

        try:
            result = self.hl_exchange.bulk_orders(
                [order_request], 
                builder={
                    "b": BASED_BUILDER_ADDRESS.lower(),
                    "f": BASED_BUILDER_FEE
                }
            )
            if result['status'] == 'ok':
                statuses = result['response']['data']['statuses']
                first = statuses[0]
                if 'filled' in first:
                    fill = first['filled']
                    log.info(f"✅ [HL] 체결 완료: {fill['totalSz']} @ {fill['avgPx']}")
                    return first
                elif 'error' in first:
                    log.error(f"❌ [HL] 주문 에러: {first['error']}")
                    return None
                else:
                    log.warning(f"⚠️ [HL] 미체결/취소됨 (IOC): {first}")
                    return first
            else:
                log.error(f"❌ [HL] 전송 실패: {result}")
                return None
        except Exception as e:
            log.error(f"❌ [HL] 예외 발생: {e}")
            return None
        
    def get_instrument_stats(self, ticker: str):
        try:
            for asset in self.meta['universe']:
                if asset['name'] == ticker:
                    sz_dec = asset['szDecimals']
                    min_size = 1.0 / (10 ** sz_dec) 
                    max_lev = float(asset['maxLeverage'])
                    return {'min_size': min_size, 'max_lev': max_lev}
        except Exception: pass
        return {'min_size': 0.0, 'max_lev': 0.0}

    async def set_leverage(self, symbol: str, leverage: int):
        try:
            if not self.exchange: return None
            coin = symbol
            if settings and symbol in settings.TARGET_PAIRS_CONFIG:
                 coin = settings.TARGET_PAIRS_CONFIG[symbol]['symbols'].get('hyperliquid', symbol)
            
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None, 
                lambda: self.exchange.update_leverage(leverage, coin, is_cross=True)
            )
            log.info(f"⚙️ [HL] {coin} 레버리지 {leverage}x 설정 완료")
            return res
        except Exception as e:
            if "already" in str(e).lower(): return
            log.warning(f"⚠️ [HL] 레버리지 설정 실패 ({symbol}): {e}")

    def _round_px(self, price):
        if not price: return 0.0
        return float(f"{price:.5g}")

    def _round_sz(self, coin, size):
        if coin not in self.coin_map: return size
        decimals = self.coin_map[coin]['szDecimals']
        return round(size, decimals)

    async def create_order(self, ticker: str, side: str, price: float, qty: float, reduce_only: bool = False, order_type='LIMIT'):
        try:
            if not self.exchange: return None
            safe_price = self._round_px(price)
            safe_qty = self._round_sz(ticker, qty)
            is_buy = True if side.upper() == 'BUY' else False
            tif = "Ioc" if reduce_only else "Gtc"
            
            cloid_obj = Cloid(BASED_CLOID_STR)

            order_request = {
                "coin": ticker, "is_buy": is_buy, "sz": safe_qty, "limit_px": safe_price,
                "order_type": {"limit": {"tif": tif}}, "reduce_only": reduce_only, "cloid": cloid_obj
            }
            log.info(f"🚀 [HL Order] {side} {ticker} {safe_qty} @ {safe_price} (Reduce: {reduce_only})")
            
            return self.exchange.bulk_orders([order_request], builder={"b": BASED_BUILDER_ADDRESS, "f": BASED_BUILDER_FEE})
        except Exception as e:
            log.error(f"[HL] Order Failed: {e}")
            return None

    async def get_balance(self):
        try:
            # user_state 호출 시 메인 주소 사용
            target_addr = self.vault_address if self.vault_address else self.main_address
            state = self.info.user_state(target_addr)
            margin = state.get('marginSummary', {})
            positions = state.get('assetPositions', [])
            return {'equity': float(margin.get('accountValue', 0)), 'positions': positions}
        except Exception as e:
            log.error(f"[HL] Get Balance Failed: {e}")
            return None

    async def close_position(self, ticker: str):
        try:
            target_addr = self.vault_address if self.vault_address else self.main_address
            state = self.info.user_state(target_addr)
            positions = state.get('assetPositions', [])
            target_pos = next((p['position'] for p in positions if p['position']['coin'] == ticker), None)
            
            if not target_pos: return None
            size = float(target_pos.get('szi', 0))
            if size == 0: return None

            close_side = 'BUY' if size < 0 else 'SELL'
            mids = self.info.all_mids()
            curr_price = float(mids.get(ticker, 0))
            limit_price = curr_price * 1.05 if close_side == 'BUY' else curr_price * 0.95
            
            return await self.create_order(ticker, close_side, limit_price, abs(size), reduce_only=True)
        except Exception as e:
            log.error(f"[HL] Close Position Failed: {e}")
            return None

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

class GrvtExchange(Exchange):
    def __init__(self):
        super().__init__()
        
        self.grvt = None
        if GrvtCcxtWS and GrvtEnv:
            try:
                # [수정됨] .env에서 정확히 키 로드
                api_key = os.getenv('GRVT_API_KEY', '')
                # 어떤 환경 변수명일지 몰라 둘 다 시도
                private_key = os.getenv('GRVT_PRIVATE_KEY', '') or os.getenv('GRVT_SECRET_KEY', '')
                sub_account_id = os.getenv('GRVT_TRADING_ACCOUNT_ID', '') # 여기가 핵심!

                if not sub_account_id:
                    log.error("❌ [GRVT] .env에 'GRVT_TRADING_ACCOUNT_ID'가 없습니다! 주문 불가능.")
                
                params = {
                    'api_key': api_key,
                    'private_key': private_key,
                    'trading_account_id': sub_account_id  # SDK에 전달
                }

                # Event Loop 처리
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                self.grvt = GrvtCcxtWS(
                    env=GrvtEnv.PROD, 
                    loop=loop, 
                    parameters=params
                )
                self.ws = self.grvt  # <-- [추가] TradeSizer와의 호환성을 위해 ws 변수도 할당
                log.info(f"✅ [GRVT] 초기화 (SubAccount: {sub_account_id})")
                
            except Exception as e:
                log.error(f"❌ [GRVT] 초기화 에러: {e}")

    async def load_markets(self):
        log.info("⏳ [GRVT] 시장 정보 로딩...")
        try:
            if self.grvt:
                await self.grvt.initialize()
                markets = self.grvt.markets
                for symbol, market in markets.items():
                    base = market.get('base', symbol.split('_')[0])
                    
                    # [핵심 수정] API의 min_size 필드를 직접 읽어 정밀도 계산
                    # API 응답 예: {'min_size': '0.001', ...}
                    raw_min_size = market.get('min_size')
                    
                    if raw_min_size:
                        amount_prec = float(raw_min_size)
                        min_amount = float(raw_min_size)
                    else:
                        # Fallback (기존 로직)
                        amount_prec = market.get('precision', {}).get('amount', 0.0001)
                        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.0001)
                    
                    # 정밀도 계산 (0.001 -> 3, 0.01 -> 2)
                    if isinstance(amount_prec, float):
                        if amount_prec > 0:
                            qty_prec = int(round(-math.log10(amount_prec), 0))
                        else:
                            qty_prec = 4
                    else:
                        qty_prec = int(amount_prec)

                    self.market_info[base] = {
                        'qty_prec': qty_prec,
                        'min_size': float(min_amount)
                    }
                log.info(f"✅ [GRVT] 로드 완료 ({len(markets)}개)")
            else:
                log.warning("⚠️ GRVT 클라이언트 없음")
        except Exception as e:
            log.warning(f"⚠️ [GRVT] 로드 실패: {e}")
            # 안전한 기본값 (BTC 3자리, ETH 2자리)
            self.market_info['BTC'] = {'qty_prec': 3, 'min_size': 0.001}
            self.market_info['ETH'] = {'qty_prec': 2, 'min_size': 0.01}

    async def place_market_order(self, symbol: str, side: str, amount: float, price: float = None):
        base_symbol = symbol.split('_')[0] if '_' in symbol else symbol
        full_symbol = f"{base_symbol}_USDT_Perp" 
        
        # [중요] load_markets에서 가져온 올바른 정밀도로 자르기
        validated_amount = self.validate_amount(base_symbol, amount)
        if validated_amount <= 0: return None

        log.info(f"🚀 [GRVT Order] {side} {full_symbol} {validated_amount}")

        try:
            if not self.grvt: return None
            
            response = await self.grvt.create_order(
                symbol=full_symbol,
                order_type='market',
                side=side.lower(),
                amount=validated_amount
            )
            
            order_id = (
                response.get('order_id') or 
                response.get('id') or 
                response.get('result', {}).get('order_id')
            )
            
            if order_id is not None:
                log.info(f"✅ [GRVT] 주문 접수 완료 (ID: {order_id})")
                return response
            else:
                log.error(f"❌ [GRVT] 주문 응답 이상: {response}")
                return None

        except Exception as e:
            log.error(f"❌ [GRVT] 주문 실패: {e}")
            return None
        
    async def connect(self):
        if not GrvtCcxtWS: return False
        try:
            if self.ws: return True 
            loop = asyncio.get_running_loop()
            quiet_logger = logging.getLogger("quiet"); quiet_logger.setLevel(logging.ERROR)
            params = {'api_key': self.api_key, 'private_key': self.private_key, 'trading_account_id': self.sub_account_id}
            
            self.ws = GrvtCcxtWS(env=GrvtEnv.PROD, loop=loop, logger=quiet_logger, parameters=params)
            await self.ws.initialize()
            await self.ws.load_markets() 
            log.info("[GRVT] Connected & Markets Loaded")
            return True
        except Exception as e:
            log.error(f"[GRVT] Connection Failed: {e}")
            return False

    def get_instrument_stats(self, ticker: str):
        """[수정] 이미 로드된 market_info에서 정확한 값을 가져옴"""
        try:
            if ticker in self.market_info:
                info = self.market_info[ticker]
                # GRVT는 보통 최대 레버리지가 20배이므로 기본값 설정
                return {'min_size': info['min_size'], 'max_lev': 20.0}
        except Exception: pass
        return {'min_size': 0.001, 'max_lev': 10.0}

    async def set_leverage(self, symbol: str, leverage: int):
        log.info(f"⚙️ [GRVT] {symbol} 레버리지: Cross Mode 사용 (자동)")

    def _get_correct_symbol(self, ticker: str) -> str:
        found = next((k for k, v in self.reverse_map.items() if v == ticker), None)
        if found: return found
        if "_USDT_" in ticker: return ticker
        return f"{ticker}_USDT_Perp"

    async def create_order(self, ticker: str, side: str, price: float, qty: float, reduce_only: bool = False, order_type='LIMIT'):
        try:
            if not self.ws: await self.connect()
            
            symbol = self._get_correct_symbol(ticker)
            safe_qty = float(qty)
            safe_price = float(price) if price else None
            safe_side = side.lower() 

            log.info(f"🚀 [GRVT Order] {order_type} {safe_side} {symbol} {safe_qty} @ {safe_price}")
            
            if order_type.upper() == 'MARKET':
                return await self.ws.rpc_create_order(
                    symbol=symbol,
                    side=safe_side,
                    order_type='market',
                    amount=safe_qty,
                    price=None, 
                    params={'reduce_only': reduce_only}
                )
            else:
                return await self.ws.rpc_create_limit_order(
                    symbol=symbol,
                    side=safe_side,
                    amount=safe_qty,
                    price=safe_price
                )

        except Exception as e:
            log.error(f"[GRVT] Order Failed: {e}")
            return None

    async def get_balance(self):
        try:
            if not self.ws: await self.connect()
            balance = await self.ws.fetch_balance()
            equity = float(balance.get('USDT', {}).get('total', 0.0))
            
            raw_positions = await self.ws.fetch_positions()
            positions = []
            
            for p in raw_positions:
                size = float(p.get('size') or p.get('contracts') or p.get('amount') or 0)
                if size != 0:
                    p['size'] = size
                    positions.append(p)
                    
            return {'equity': equity, 'positions': positions}
        except Exception as e:
            log.error(f"[GRVT] Get Balance Failed: {e}")
            return None

    async def close_position(self, ticker: str):
        try:
            if not self.ws: await self.connect()
            
            positions = await self.ws.fetch_positions()
            target_pos = None
            
            for pos in positions:
                p_sym = pos.get('instrument', pos.get('symbol', ''))
                if ticker in p_sym or p_sym in ticker:
                    target_pos = pos
                    break
            
            if not target_pos:
                print(f"⚠️ {ticker} 포지션 없음")
                return

            size = float(target_pos.get('size') or target_pos.get('contracts') or target_pos.get('amount') or 0)
            if size == 0: return

            side = 'buy' if size < 0 else 'sell'
            abs_qty = abs(size)

            print(f"🧹 [청산] {ticker} {abs_qty} {side.upper()} 주문")
            
            real_symbol = target_pos.get('instrument', target_pos.get('symbol'))
            
            return await self.ws.rpc_create_order(
                symbol=real_symbol,
                side=side,
                order_type='market',
                amount=abs_qty,
                price=None,
                params={'reduce_only': True}
            )

        except Exception as e:
            print(f"❌ 포지션 청산 중 오류: {e}")
            return None

    async def close(self):
        self.ws_running = False
        try:
            if self.ws and hasattr(self.ws, '_session') and self.ws._session:
                if not self.ws._session.closed:
                    await self.ws._session.close()
        except: pass

    async def start_ws(self, callback: Callable):
        if not self.ws: await self.connect()
        try:
            def make_callback(instr):
                async def wrapped(msg):
                    feed = msg.get("feed")
                    if feed:
                        bids = feed.get('bids', [])
                        asks = feed.get('asks', [])
                        if bids and asks:
                            bot_sym = self.reverse_map.get(instr)
                            if bot_sym:
                                best_bid = float(bids[0]['price'])
                                best_ask = float(asks[0]['price'])
                                bbo = self._validate_and_format('grvt', bot_sym, best_bid, best_ask)
                                if bbo:
                                    self.bbo_cache[bot_sym] = bbo
                                    await callback(bbo)
                return wrapped

            for instr in self.target_instruments:
                if instr:
                    await self.ws.subscribe(stream='book.s', callback=make_callback(instr), params={'instrument': instr})
                    await asyncio.sleep(0.1)
        except: pass
        
        while self.ws_running: await asyncio.sleep(1)

# 4. Pacifica
# ==========================================
# 4. Pacifica Implementation (Agent Key + WS Mapping 통합)
# ==========================================
class PacificaExchange(Exchange):
    def __init__(self, main_address: str, agent_private_key: str):
        super().__init__()
        self.rest_url = "https://api.pacifica.fi/api/v1"
        self.ws_url = "wss://ws.pacifica.fi/ws"
        
        # 1. 인증 정보 설정
        self.main_address = main_address
        self.agent_private_key = agent_private_key
        self.agent_keypair = None
        self.agent_public_key = None

        if not base58 or not Keypair:
            log.error("❌ [Pacifica] 'solders' 또는 'base58' 라이브러리 누락")
        else:
            try:
                self.agent_keypair = Keypair.from_base58_string(self.agent_private_key)
                self.agent_public_key = str(self.agent_keypair.pubkey())
                log.info(f"✅ [Pacifica] 초기화 완료 (Main: {self.main_address[:6]}..)")
            except Exception as e:
                log.error(f"❌ [Pacifica] 키페어 생성 실패: {e}")

        # 2. 마켓 기본 정보 (Fallback)
        self.market_info = {
            "BTC": {"qty_prec": 3, "min_size": 0.001},
            "ETH": {"qty_prec": 3, "min_size": 0.01},
            "SOL": {"qty_prec": 2, "min_size": 0.1},
        }

        # 3. [복구됨] 심볼 매핑 로직 (settings.py 참조)
        self.target_mapping = {}
        self.virtual_spread = PAC_SPREAD
        
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'pacifica' in cfg['symbols']:
                    sym = cfg['symbols']['pacifica']
                    if sym:
                        # 기본 심볼 매핑 (예: BTC -> BTC)
                        self.target_mapping[sym.upper()] = t
                        
                        # 변형 케이스 매핑 (kBONK -> 1000BONK 등)
                        if sym.startswith('k'): 
                            self.target_mapping[sym[1:].upper()] = t
                        if sym.startswith('1000'): 
                            self.target_mapping[sym.replace('1000', '').upper()] = t

    # --- 서명 생성 헬퍼 ---
    def _create_signature(self, req_type: str, payload: Dict):
        timestamp = int(time.time() * 1000)
        expiry_window = 5000 
        
        signature_header = {
            "timestamp": timestamp, "expiry_window": expiry_window, "type": req_type
        }
        
        def sort_json_keys(value):
            if isinstance(value, dict): return {k: sort_json_keys(v) for k in sorted(value.keys())}
            elif isinstance(value, list): return [sort_json_keys(i) for i in value]
            else: return value

        data = {**signature_header, "data": payload}
        sorted_data = sort_json_keys(data)
        message_bytes = json.dumps(sorted_data, separators=(",", ":")).encode("utf-8")
        
        signature_bytes = self.agent_keypair.sign_message(message_bytes)
        signature = base58.b58encode(bytes(signature_bytes)).decode("ascii")
        
        request_header = {
            "account": self.main_address,
            "agent_wallet": self.agent_public_key,
            "signature": signature,
            "timestamp": timestamp,
            "expiry_window": expiry_window,
        }
        return request_header

    async def load_markets(self):
        # API 제공 정보가 제한적이므로 기본 설정 사용
        pass

    async def place_market_order(self, symbol: str, side: str, amount: float, price: float = None):
        # 봇 내부 심볼(예: 1000BONK)을 파시피카 심볼로 변환해야 할 수도 있음
        # 여기서는 기본적으로 앞부분만 잘라서 사용 (BTC_USDT -> BTC)
        target_symbol = symbol.split('_')[0] 
        
        # k 접두어 처리 로직 (필요시 활성화)
        # if target_symbol.startswith('1000'): target_symbol = 'k' + target_symbol[4:]

        validated_amount = self.validate_amount(target_symbol, amount)
        if validated_amount <= 0: return None

        order_side = "bid" if side.upper() == "BUY" else "ask"
        
        payload = {
            "symbol": target_symbol,
            "reduce_only": False,
            "amount": f"{validated_amount}",
            "side": order_side,
            "slippage_percent": "0.5",
            "client_order_id": str(uuid.uuid4())
        }

        req_header = self._create_signature("create_market_order", payload)
        request_body = {**req_header, **payload}
        url = f"{self.rest_url}/orders/create_market"
        headers = {"Content-Type": "application/json"}

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: requests.post(url, json=request_body, headers=headers))
            
            try: res_json = response.json()
            except: res_json = {}

            if response.status_code == 200 and res_json.get('success') is True:
                log.info(f"🚀 [Pacifica] 주문 성공: {symbol} {side} {validated_amount}")
                return res_json
            else:
                log.error(f"❌ [Pacifica] 주문 실패: {res_json}")
                return None
        except Exception as e:
            log.error(f"❌ [Pacifica] 주문 중 예외 발생: {e}")
            return None

    async def get_balance(self):
        try:
            loop = asyncio.get_running_loop()
            
            # 1. 잔고 조회 (GET /account)
            acc_url = f"{self.rest_url}/account"
            acc_params = {"account": self.main_address}
            acc_resp = await loop.run_in_executor(None, lambda: requests.get(acc_url, params=acc_params))
            
            equity = 0.0
            if acc_resp.status_code == 200:
                acc_data = acc_resp.json().get('data', {})
                equity = float(acc_data.get('account_equity', 0))

            # 2. 포지션 조회 (GET /positions)
            pos_url = f"{self.rest_url}/positions"
            pos_params = {"account": self.main_address}
            pos_resp = await loop.run_in_executor(None, lambda: requests.get(pos_url, params=pos_params))
            
            positions = []
            if pos_resp.status_code == 200:
                pos_list = pos_resp.json().get('data', [])
                for p in pos_list:
                    size = float(p.get('amount', 0))
                    if size != 0:
                        raw_side = p.get('side', '').lower()
                        side = 'LONG' if raw_side in ['bid', 'buy', 'long'] else 'SHORT'
                        
                        # 원본 심볼에서 봇 심볼로 매핑 (Reverse Mapping)
                        raw_sym = p.get('symbol', '').upper()
                        # 매핑 테이블에 있으면 변환, 없으면 그대로 사용
                        bot_symbol = self.target_mapping.get(raw_sym, raw_sym)

                        positions.append({
                            'symbol': bot_symbol,
                            'size': abs(size),
                            'amount': abs(size),
                            'side': side,
                            'entry_price': float(p.get('entry_price', 0))
                        })

            return {'equity': equity, 'positions': positions}

        except Exception as e:
            log.error(f"❌ [Pacifica] 잔고 조회 에러: {e}")
            return None

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://pacifica.fi"}
        log.info(f"[Pacifica] Connecting... (Spread: {self.virtual_spread*100}%)")
        
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers, ping_interval=None) as ws:
                    await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
                    log.info("[Pacifica] 가격 구독 완료")
                    
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        
                        if data.get("channel") == "prices":
                            payload = data.get("data", [])
                            items = payload if isinstance(payload, list) else [payload]
                            
                            for item in items:
                                raw_sym = item.get("symbol", "").upper()
                                # [수정됨] 매핑된 티커 사용
                                ticker = self.target_mapping.get(raw_sym)
                                
                                if ticker:
                                    price = float(item.get("mark") or item.get("oracle") or 0)
                                    if price > 0:
                                        bbo = self._validate_and_format(
                                            'pacifica', ticker, 
                                            price * (1 - self.virtual_spread), 
                                            price * (1 + self.virtual_spread),
                                            10000, 10000
                                        )
                                        if bbo:
                                            self.bbo_cache[ticker] = bbo
                                            await callback(bbo)
            except Exception as e:
                log.warning(f"[Pacifica] WS 재연결 대기: {e}")
                await asyncio.sleep(5)

# 5. Extended, 6. Lighter (생략 - 기존 유지)
class ExtendedExchange(Exchange):
    def __init__(self, private_key: str, address: str = None):
        super().__init__()
        self.base_url = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1"
        self.targets = {}
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'extended' in cfg['symbols']:
                    sym = cfg['symbols']['extended']
                    if sym and sym != "None": self.targets[sym] = t

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

class LighterExchange(Exchange):
    def __init__(self, api_key: str, public_key: str):
        super().__init__()
        self.ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
        self.id_map = {} 
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'lighter' in cfg['symbols']:
                    val = cfg['symbols']['lighter']
                    try:
                        if val is not None and isinstance(val, int): self.id_map[val] = t
                    except: pass

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