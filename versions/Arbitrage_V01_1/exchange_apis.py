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
except ImportError:
    settings = None

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

# 로그 설정
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

    @abstractmethod
    async def start_ws(self, callback: Callable):
        pass

    def get_bbo(self, ticker: str) -> Optional[Dict]:
        return self.bbo_cache.get(ticker)

    async def close(self):
        self.ws_running = False
        
    def _log_heartbeat(self, exchange_name, ticker, price):
        if time.time() - self.last_log_time > 10:
            log.info(f"💓 [{exchange_name}] {ticker} 수신 중 (${price})")
            self.last_log_time = time.time()

# 2. Hyperliquid
class HyperliquidExchange(Exchange):
    def __init__(self, private_key: str, address: str):
        super().__init__()
        self.private_key = private_key
        self.address = address
        self.info = None
        self.target_symbols = []
        if settings:
            for ticker, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'hyperliquid' in cfg['symbols']:
                    self.target_symbols.append(cfg['symbols']['hyperliquid'])

    def _on_bbo_update(self, data: Dict):
        try:
            content = data.get('data', data)
            coin = content.get('coin')
            levels = content.get('levels')
            if levels and len(levels) == 2:
                bids = levels[0]; asks = levels[1]
                if bids and asks:
                    best_bid = float(bids[0]['px'])
                    best_ask = float(asks[0]['px'])
                    bbo = {'symbol': coin, 'bid': best_bid, 'ask': best_ask, 'exchange': 'hyperliquid', 'timestamp': time.time()}
                    self.bbo_cache[coin] = bbo
                    self._log_heartbeat('HL', coin, best_bid)
                    if self.main_callback and self.loop:
                        asyncio.run_coroutine_threadsafe(self.main_callback(bbo), self.loop)
        except: pass

    async def start_ws(self, callback: Callable):
        if not Info: return
        self.main_callback = callback
        self.loop = asyncio.get_running_loop()
        self.ws_running = True
        log.info(f"[HL] 연결 시도 ({len(self.target_symbols)}개 심볼)")
        try:
            self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=False)
            chunk_size = 50
            for i in range(0, len(self.target_symbols), chunk_size):
                chunk = self.target_symbols[i:i+chunk_size]
                for coin in chunk:
                    self.info.subscribe({"type": "l2Book", "coin": coin}, self._on_bbo_update)
                await asyncio.sleep(0.1) 
            log.info("[HL] 모든 구독 완료 ✅")
        except Exception as e:
            log.error(f"[HL] 연결 에러: {e}")
            return
        while self.ws_running: await asyncio.sleep(1)

# 3. GRVT
class GrvtExchange(Exchange):
    def __init__(self, api_key: str, secret_key: str, account_id: str):
        super().__init__()
        self.api_key = api_key; self.secret_key = secret_key; self.account_id = account_id
        self.ws = None
        self.target_instruments = []
        if settings:
            for ticker, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'grvt' in cfg['symbols']:
                    self.target_instruments.append(cfg['symbols']['grvt'])

    async def start_ws(self, callback: Callable):
        if not GrvtCcxtWS: return
        params = {'api_key': self.api_key, 'private_key': self.secret_key, 'trading_account_id': self.account_id}
        loop = asyncio.get_running_loop()
        quiet_logger = logging.getLogger("quiet"); quiet_logger.setLevel(logging.ERROR)
        self.ws = GrvtCcxtWS(env=GrvtEnv.PROD, loop=loop, logger=quiet_logger, parameters=params)
        self.ws_running = True
        await self.ws.initialize() 
        
        def make_callback(instr):
            async def wrapped(msg):
                try:
                    feed = msg.get("feed")
                    if feed:
                        bids, asks = feed.get('bids', []), feed.get('asks', [])
                        if bids and asks:
                            sym = instr.split('_')[0]
                            bbo = {'symbol': sym, 'bid': float(bids[0]['price']), 'ask': float(asks[0]['price']), 'exchange': 'grvt', 'timestamp': time.time()}
                            self.bbo_cache[sym] = bbo
                            self._log_heartbeat('GRVT', sym, bbo['bid'])
                            await callback(bbo)
                except: pass
            return wrapped

        log.info(f"[GRVT] {len(self.target_instruments)}개 구독 요청")
        for instr in self.target_instruments:
            await self.ws.subscribe(stream='book.s', callback=make_callback(instr), params={'instrument': instr, 'depth': 10})
            await asyncio.sleep(0.01)
        while self.ws_running: await asyncio.sleep(1)

# 4. Pacifica
class PacificaExchange(Exchange):
    def __init__(self, private_key: str, address: str = None):
        super().__init__()
        self.ws_url = "wss://ws.pacifica.fi/ws"
        self.target_mapping = {}
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'pacifica' in cfg['symbols']:
                    self.target_mapping[cfg['symbols']['pacifica']] = t

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://pacifica.fi"}
        log.info("[Pacifica] Connecting...")
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers, ping_interval=30) as ws:
                    await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
                    log.info("[Pacifica] 구독 완료")
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        if data.get("channel") == "prices":
                            if "data" in data and isinstance(data["data"], list):
                                for item in data["data"]:
                                    sym = item.get("symbol")
                                    if sym in self.target_mapping:
                                        ticker = self.target_mapping[sym]
                                        price = float(item.get("mark") or item.get("oracle") or 0)
                                        if price > 0:
                                            bbo = {
                                                'symbol': ticker, 
                                                'bid': price * 0.9995, 'ask': price * 1.0005, 
                                                'exchange': 'pacifica', 'timestamp': time.time()
                                            }
                                            self.bbo_cache[ticker] = bbo
                                            self._log_heartbeat('Pacifica', ticker, price)
                                            await callback(bbo)
            except Exception as e:
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
                    if sym and sym != "None":
                        self.targets[sym] = t

    async def _maintain_socket(self, symbol: str, ticker: str, callback: Callable):
        url = f"{self.base_url}/orderbooks/{symbol}"
        ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
        while self.ws_running:
            try:
                async with websockets.connect(url, ssl=ssl_ctx) as ws:
                    async for msg in ws:
                        if not self.ws_running: break
                        payload = json.loads(msg)
                        data = payload.get('data', payload)
                        bids, asks = data.get('bids', []), data.get('asks', [])
                        if bids and asks:
                            bid_p = float(bids[0]['p'] if isinstance(bids[0], dict) else bids[0][0])
                            ask_p = float(asks[0]['p'] if isinstance(asks[0], dict) else asks[0][0])
                            bbo = {
                                'symbol': ticker, 'bid': bid_p, 'ask': ask_p, 
                                'exchange': 'extended', 'timestamp': time.time()
                            }
                            self.bbo_cache[ticker] = bbo
                            self._log_heartbeat('Extended', ticker, bid_p)
                            await callback(bbo)
            except: await asyncio.sleep(5)

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        tasks = []
        for sym, ticker in self.targets.items():
            tasks.append(asyncio.create_task(self._maintain_socket(sym, ticker, callback)))
            await asyncio.sleep(0.1)
        log.info(f"[Extended] {len(tasks)}개 소켓 연결 중...")
        await asyncio.gather(*tasks)

# 6. Lighter (ID 기반 정밀 구독)
class LighterExchange(Exchange):
    def __init__(self, api_key: str, public_key: str):
        super().__init__()
        self.ws_url = "wss://mainnet.zklighter.elliot.ai/stream"
        self.id_map = {} 
        if settings:
            for t, cfg in settings.TARGET_PAIRS_CONFIG.items():
                if 'lighter' in cfg['symbols']:
                    val = cfg['symbols']['lighter']
                    # 정수 ID만 로드 (추측 방지)
                    try:
                        if val is not None and isinstance(val, int):
                            self.id_map[val] = t
                    except: pass

    async def start_ws(self, callback: Callable):
        self.ws_running = True
        headers = {"User-Agent": "Mozilla/5.0"}
        log.info(f"[Lighter] {len(self.id_map)}개 ID 구독 시작 (Settings 기반)")
        
        while self.ws_running:
            try:
                async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                    # 설정된 ID만 정확하게 구독
                    for mid in self.id_map.keys():
                        await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{mid}"}))
                        
                    async for msg in ws:
                        if not self.ws_running: break
                        data = json.loads(msg)
                        if data.get('type') == 'ping': await ws.send(json.dumps({"type": "pong"})); continue
                        
                        if data.get('type') == 'update/order_book':
                            channel = data.get('channel', '')
                            try:
                                # order_book:1 형태 파싱
                                mid = int(channel.split(':')[1]) if ':' in channel else int(channel.split('/')[1])
                                
                                if mid in self.id_map:
                                    ticker = self.id_map[mid]
                                    ob = data.get('order_book', {})
                                    bids, asks = ob.get('bids', []), ob.get('asks', [])
                                    if bids and asks:
                                        best_bid = float(bids[0]['price'])
                                        best_ask = float(asks[0]['price'])
                                        
                                        # [최종 안전장치] 가격이 0.1 미만인 메이저 코인 필터링 (데이터 오류 방지)
                                        if ticker in ['BTC', 'ETH', 'BNB', 'SOL'] and best_bid < 1.0:
                                            continue

                                        bbo = {
                                            'symbol': ticker, 'bid': best_bid, 'ask': best_ask, 
                                            'exchange': 'lighter', 'timestamp': time.time()
                                        }
                                        self.bbo_cache[ticker] = bbo
                                        self._log_heartbeat('Lighter', ticker, best_bid)
                                        await callback(bbo)
                            except: pass
            except: await asyncio.sleep(5)