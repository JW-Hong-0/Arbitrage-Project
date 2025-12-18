import asyncio
import aiohttp
import json
import websockets
import ssl
import logging
import sys
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ID_Finder")

HEADERS = {"User-Agent": "Mozilla/5.0"}

async def find_lighter_ids():
    """Lighter: 0~100번 ID를 구독해서 무슨 코인인지 밝혀냅니다."""
    logger.info("\n⚪ [Lighter] ID 0~100 전수 조사 중...")
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    
    found = {}
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS) as ws:
            # 1. 대량 구독 요청
            for i in range(100):
                await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{i}"}))
            
            # 2. 5초간 데이터 수집
            start = time.time()
            while time.time() - start < 5:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    data = json.loads(msg)
                    
                    if data.get("type") == "update/order_book":
                        chan = data.get("channel", "") # order_book/1
                        mid = int(chan.split("/")[1])
                        
                        # 가격 확인
                        ob = data.get("order_book", {})
                        bids = ob.get("bids", [])
                        if bids and mid not in found:
                            price = float(bids[0]['price'])
                            
                            # 이름 추정 (로그용) - 실제 매핑은 사용자가 settings.py에서 확정
                            name = "Unknown"
                            if price > 80000: name = "BTC"
                            elif price > 2000: name = "ETH"
                            elif price > 200 and price < 400: name = "BNB/BCH?"
                            elif price > 100: name = "SOL"
                            elif price > 1.0: name = "XRP/SUI/ARB?"
                            
                            found[mid] = f"{name} (${price})"
                            logger.info(f"   ✅ ID {mid}: {found[mid]}")
                except: break
    except Exception as e: logger.error(f"   ❌ 연결 실패: {e}")
    
    return found

async def find_pacifica_symbols():
    """Pacifica: 전체 심볼 리스트 수집"""
    logger.info("\n🔵 [Pacifica] 전체 심볼 수집 중...")
    url = "wss://ws.pacifica.fi/ws"
    found = []
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, ping_interval=20) as ws:
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            
            start = time.time()
            while time.time() - start < 3:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data.get("channel") == "prices" and "data" in data:
                        for item in data["data"]:
                            found.append(item['symbol'])
                        break # 한 번만 받으면 됨
                except: pass
    except: pass
    
    logger.info(f"   ✅ {len(found)}개 발견: {found[:5]}...")
    return found

async def find_extended_symbols():
    """Extended: 주요 코인 존재 여부 확인"""
    logger.info("\n🟣 [Extended] 주요 마켓 연결 테스트...")
    url_base = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    
    targets = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "DOGE-USD"]
    confirmed = []
    
    ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
    
    for t in targets:
        try:
            async with websockets.connect(f"{url_base}/{t}", ssl=ssl_ctx) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                if "bids" in msg or "data" in msg:
                    confirmed.append(t)
                    logger.info(f"   ✅ {t}: 연결 성공")
        except:
            logger.warning(f"   ⚠️ {t}: 연결 실패")
            
    return confirmed

async def main():
    print("="*60)
    print("🕵️‍♂️ 거래소 ID/심볼 정밀 채굴기")
    print("="*60)
    
    ltr_ids = await find_lighter_ids()
    pac_syms = await find_pacifica_symbols()
    ext_syms = await find_extended_symbols()
    
    print("\n" + "="*60)
    print("🚀 [settings.py] 업데이트용 데이터")
    print("="*60)
    print(f"Lighter IDs: {json.dumps(ltr_ids, indent=2)}")
    print(f"Pacifica Symbols: {pac_syms}")
    print(f"Extended Markets: {ext_syms}")
    print("="*60)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())