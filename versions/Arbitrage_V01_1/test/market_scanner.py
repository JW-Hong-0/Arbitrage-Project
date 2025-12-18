import asyncio
import aiohttp
import json
import logging
import sys
import websockets
import ssl

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Scanner")

HEADERS = {"User-Agent": "Mozilla/5.0"}

async def get_lighter_map():
    """Lighter: API 문서 기반 정확한 ID 매핑"""
    logger.info("\n⚪ [Lighter] 공식 마켓 리스트 다운로드...")
    url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # [수정] 사용자 제보: 'order_books' 키 사용
                    items = data.get("order_books", [])
                    
                    mapping = {}
                    for item in items:
                        # symbol: "BTC", market_id: 1
                        sym = item.get('symbol')
                        mid = item.get('market_id')
                        
                        if sym and mid is not None:
                            mapping[sym] = int(mid)
                            
                    logger.info(f"   ✅ 성공! {len(mapping)}개 마켓 ID 확보")
                    return mapping
    except Exception as e:
        logger.error(f"   ❌ 실패: {e}")
    return {}

async def get_extended_verified_list():
    """Extended: 웹소켓으로 실존 여부 검증 (REST 실패 대비)"""
    logger.info("\n🟣 [Extended] 주요 마켓 연결 검증...")
    url_base = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
    
    # 검증할 후보군 (주요 코인 + Lighter/Pacifica에 있는 것들)
    candidates = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'AVAX', 'SUI', 'ARB', 'OP', 'LTC', 'TIA', 'STRK', 'LINK', 'TRUMP']
    verified = []
    
    for t in candidates:
        sym = f"{t}-USD"
        try:
            async with websockets.connect(f"{url_base}/{sym}", ssl=ssl_ctx, open_timeout=2) as ws:
                # 연결 되자마자 SNAPSHOT이 오는지 확인
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    if "m" in msg or "b" in msg: # m: market, b: bids
                        verified.append(sym)
                        # logger.info(f"   ✅ {sym} 확인")
                except: pass
        except: pass
        
    logger.info(f"   ✅ 총 {len(verified)}개 마켓 검증 완료")
    return verified

async def get_pacifica_list():
    """Pacifica: 전체 심볼 수신"""
    logger.info("\n🔵 [Pacifica] 마켓 리스트 수신 중...")
    url = "wss://ws.pacifica.fi/ws"
    found = set()
    try:
        async with websockets.connect(url, extra_headers=HEADERS, ping_interval=20) as ws:
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < 3:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    data = json.loads(msg)
                    if data.get("channel") == "prices":
                        for item in data.get("data", []):
                            s = item.get("symbol")
                            if s: found.add(s)
                except: pass
    except: pass
    logger.info(f"   ✅ {len(found)}개 심볼 확보")
    return list(found)

async def main():
    # 1. 팩트 수집
    ltr_map = await get_lighter_map()
    ext_list = await get_extended_verified_list()
    pac_list = await get_pacifica_list()
    
    # 2. 통합 설정 생성
    print("\n" + "="*60)
    print("🚀 [settings.py] 최종 설정값 (복사해서 덮어쓰세요)")
    print("="*60)
    
    # 합집합 생성
    all_tickers = set(ltr_map.keys()) | set(pac_list) | set([x.split('-')[0] for x in ext_list])
    majors = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'AVAX', 'SUI']
    sorted_tickers = sorted(list(all_tickers), key=lambda x: (0 if x in majors else 1, x))
    
    print("TARGET_PAIRS_CONFIG = {")
    
    for t in sorted_tickers:
        # 각 거래소별 심볼/ID 결정
        
        # Lighter: 맵에 있으면 ID(숫자) 사용
        ltr_val = ltr_map.get(t)
        ltr_str = f"{ltr_val}" if ltr_val is not None else "None"
        
        # Pacifica: 리스트에 있으면 심볼 사용
        pac_val = f'"{t}"' if t in pac_list else "None"
        
        # Extended: 검증된 리스트에 있으면 사용
        ext_target = f"{t}-USD"
        ext_val = f'"{ext_target}"' if ext_target in ext_list else "None"
        
        # Hyperliquid, GRVT는 기본 지원 가정
        
        # 유효성 검사 (2개 이상 거래소에서 지원해야 함)
        valid_cnt = 2 # HL, GRVT
        if ltr_val is not None: valid_cnt += 1
        if t in pac_list: valid_cnt += 1
        if ext_target in ext_list: valid_cnt += 1
        
        if valid_cnt >= 3: # HL, GRVT 포함 3개 이상이면 추가
            preset = "major" if t in majors else "volatile"
            size = 50.0 if t in majors else 20.0
            
            print(f'    "{t}": {{')
            print(f'        "symbols": {{')
            print(f'            "hyperliquid": "{t}",')
            print(f'            "grvt": "{t}_USDT_Perp",')
            print(f'            "pacifica": {pac_val},')
            print(f'            "extended": {ext_val},')
            print(f'            "lighter": {ltr_str},')
            print(f'        }},')
            print(f'        "strategy_preset": "{preset}",')
            print(f'        "trade_size_fixed_usd": {size}')
            print(f'    }},')

    print("}")
    print("="*60)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())