import asyncio
import logging
import json
import websockets
import ssl
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable
import sys
import time

# --- 설정 파일 로드 ---
try:
    import settings
    PAC_SPREAD = getattr(settings, 'PACIFICA_VIRTUAL_SPREAD', 0.0005)
except ImportError:
    settings = None
    PAC_SPREAD = 0.0005

# --- 외부 라이브러리 ---
try:
    from hyperliquid.info import Info
    from hyperliquid.utils import constants as hl_constants
except ImportError:
    Info = None

try:
    from pysdk.grvt_ccxt_ws import GrvtCcxtWS
    from pysdk.grvt_ccxt_env import GrvtEnv
except ImportError:
    GrvtCcxtWS = None

logging.getLogger("pysdk").setLevel(logging.ERROR) 
logging.getLogger("GrvtCcxtWS").setLevel(logging.ERROR)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger("ExchangeAPIs")
log.setLevel(logging.INFO)

# 1. Base Interface
class Exchange(ABC):
    def __init__(self):
        self.ws_running = False
        self.bbo_cache = {} 
        self.last_log_time = 0
        self.last_prices = {} 

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
        
        # [수정] 필터 기준 강화: 20% -> 1% (0.01)
        # 암호화폐라도 1초도 안 되는 시간에 1%가 움직이는 건 노이즈일 확률이 99%입니다.
        if last_price:
            change_pct = abs(current_mid - last_price) / last_price
            if change_pct > 0.01: 
                # log.warning(f"⚠️ [{exchange}] {symbol} Spike Ignored: {last_price:.4f} -> {current_mid:.4f} ({change_pct*100:.2f}%)")
                return None
        
        self.last_prices[symbol] = current_mid
            
        return {
            'symbol': symbol, 'bid': bid, 'ask': ask,
            'bid_qty': bid_qty, 'ask_qty': ask_qty,
            'exchange': exchange, 'timestamp': time.time()
        }

# 2. Hyperliquid
class HyperliquidExchange(Exchange):
    def __init__(self, private_key: str, address: str):
        super().__init__()
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

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        log.info(f"[HL] Connecting to allMids... (Target: {len(self.target_symbols)})")
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
                                        spread = 0.0005
                                        bbo = self._validate_and_format('hyperliquid', bot_symbol, price*(1-spread), price*(1+spread), 10000.0, 10000.0)
                                        if bbo:
                                            self.bbo_cache[bot_symbol] = bbo
                                            if bot_symbol == 'BTC': self._log_heartbeat('HL', bot_symbol, price)
                                            await callback(bbo)
                                    except: pass
            except Exception as e:
                log.warning(f"[HL] Reconnecting: {e}")
                await asyncio.sleep(5)

# 3. GRVT (안전장치 추가됨)
class GrvtExchange(Exchange):
    def __init__(self, api_key: str, secret_key: str, account_id: str):
        super().__init__()
        self.api_key = api_key; self.secret_key = secret_key; self.account_id = account_id
        self.ws = None
        self.target_instruments = []
        self.reverse_map = {} 
        if settings:
            for ticker, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'grvt' in cfg['symbols']:
                    grvt_sym = cfg['symbols']['grvt']
                    if grvt_sym: 
                        self.target_instruments.append(grvt_sym)
                        self.reverse_map[grvt_sym] = ticker 

    async def start_ws(self, callback: Callable):
        if not GrvtCcxtWS: return
        self.ws_running = True
        
        # [수정] 무한 재시도 루프 추가
        while self.ws_running:
            try:
                params = {'api_key': self.api_key, 'private_key': self.secret_key, 'trading_account_id': self.account_id}
                loop = asyncio.get_running_loop()
                quiet_logger = logging.getLogger("quiet"); quiet_logger.setLevel(logging.ERROR)
                
                self.ws = GrvtCcxtWS(env=GrvtEnv.PROD, loop=loop, logger=quiet_logger, parameters=params)
                
                # 초기화 시도 (여기서 에러나면 catch됨)
                await self.ws.initialize() 
                
                def make_callback(instr):
                    async def wrapped(msg):
                        try:
                            feed = msg.get("feed")
                            if feed:
                                bids, asks = feed.get('bids', []), feed.get('asks', [])
                                if bids and asks:
                                    bot_symbol = self.reverse_map.get(instr, instr.split('_')[0])
                                    bid_p = float(bids[0]['price'])
                                    ask_p = float(asks[0]['price'])
                                    bid_s = float(bids[0]['size'])
                                    ask_s = float(asks[0]['size'])
                                    
                                    if bot_symbol == 'RESOLV' and bid_p > 10.0: return

                                    bbo = self._validate_and_format('grvt', bot_symbol, bid_p, ask_p, bid_s, ask_s)
                                    if bbo:
                                        self.bbo_cache[bot_symbol] = bbo
                                        self._log_heartbeat('GRVT', bot_symbol, bid_p)
                                        await callback(bbo)
                        except: pass
                    return wrapped

                log.info(f"[GRVT] {len(self.target_instruments)}개 구독 요청")
                for instr in self.target_instruments:
                    if not instr: continue
                    await self.ws.subscribe(stream='book.s', callback=make_callback(instr), params={'instrument': instr, 'depth': 10})
                    await asyncio.sleep(0.01)
                
                # 연결 유지
                while self.ws_running:
                    await asyncio.sleep(1)

            except Exception as e:
                log.error(f"[GRVT] Connection Error (Retrying in 5s): {e}")
                await asyncio.sleep(5) # 5초 후 재시도

# 4. Pacifica
class PacificaExchange(Exchange):
    def __init__(self, private_key: str, address: str = None):
        super().__init__()
        self.ws_url = "wss://ws.pacifica.fi/ws"
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

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://pacifica.fi"}
        log.info(f"[Pacifica] Connecting... (Spread: {self.virtual_spread*100}%)")
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers, ping_interval=30) as ws:
                    await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
                    log.info("[Pacifica] 구독 완료")
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        if data.get("channel") == "prices":
                            payload = data.get("data", [])
                            items = payload if isinstance(payload, list) else []
                            if isinstance(payload, dict): items = [payload]
                            for item in items:
                                raw_sym = item.get("symbol", "").upper()
                                ticker = self.target_mapping.get(raw_sym)
                                if ticker:
                                    price = float(item.get("mark") or item.get("oracle") or 0)
                                    if price > 0:
                                        bbo = self._validate_and_format('pacifica', ticker, price*(1-self.virtual_spread), price*(1+self.virtual_spread), 10000, 10000)
                                        if bbo:
                                            self.bbo_cache[ticker] = bbo
                                            if ticker == 'BTC': self._log_heartbeat('Pacifica', ticker, price)
                                            await callback(bbo)
            except Exception as e:
                log.warning(f"[Pacifica] Reconnecting: {e}")
                await asyncio.sleep(5)

# 5. Extended
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
                                self._log_heartbeat('Extended', ticker, bid_p)
                                await callback(bbo)
            except: await asyncio.sleep(5)

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        tasks = [asyncio.create_task(self._maintain_socket(s, t, callback)) for s, t in self.targets.items()]
        log.info(f"[Extended] {len(tasks)}개 연결")
        await asyncio.gather(*tasks)

# 6. Lighter
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