import asyncio
import json
import logging
import websockets
import ssl
import sys

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Inspector")

# 봇 차단 방지용 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://pacifica.fi"
}

async def inspect_lighter():
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    logger.info(f"\n⚪ [1/3 Lighter] 접속 시도: {url}")
    try:
        # 타임아웃 5초 설정
        async with websockets.connect(url, open_timeout=5, extra_headers=HEADERS) as ws:
            logger.info("   ✅ 연결 성공! 데이터 구독 요청 중...")
            # ID 1번(BTC 추정) 구독 시도
            await ws.send(json.dumps({"type": "subscribe", "channel": "order_book/1"}))
            
            for _ in range(3): # 최대 3개 메시지만 확인
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                        
                    if data.get("type") == "update/order_book":
                        logger.info(f"   🎉 오더북 데이터 포착!")
                        ob = data.get("order_book", {})
                        logger.info(f"   👉 Key 구조: {list(ob.keys())}") # ['bids', 'asks', ...]
                        if ob.get('bids'):
                            logger.info(f"   👉 Bid 샘플: {ob['bids'][0]}") # ['98000', '0.1'] 형태인지 확인
                        return
                except asyncio.TimeoutError:
                    logger.warning("   ⏰ 데이터 수신 시간 초과")
                    break
    except Exception as e: logger.error(f"   ❌ 실패: {e}")

async def inspect_extended():
    # ETH-USD 예시
    url = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks/ETH-USD"
    logger.info(f"\n🟣 [2/3 Extended] 접속 시도: {url}")
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    try:
        async with websockets.connect(url, ssl=ssl_ctx, open_timeout=5, extra_headers=HEADERS) as ws:
            logger.info("   ✅ 연결 성공! 첫 번째 메시지 대기 중...")
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            
            logger.info(f"   🎉 데이터 포착!")
            # 키 확인
            logger.info(f"   👉 최상위 Keys: {list(data.keys())}") 
            if 'bids' in data:
                logger.info(f"   👉 Bid 샘플: {data['bids'][0]}")
    except Exception as e: logger.error(f"   ❌ 실패: {e}")

async def inspect_pacifica():
    url = "wss://ws.pacifica.fi/ws"
    logger.info(f"\n🔵 [3/3 Pacifica] 접속 시도: {url}")
    try:
        async with websockets.connect(url, open_timeout=5, extra_headers=HEADERS) as ws:
            logger.info("   ✅ 연결 성공! 구독 요청 중...")
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    
                    # Pacifica 응답 구조 확인
                    if isinstance(data, dict) and data.get("type") == "prices":
                        logger.info(f"   🎉 가격 데이터 포착!")
                        if data.get('data'):
                            sample = data['data'][0]
                            logger.info(f"   👉 데이터 샘플 Keys: {list(sample.keys())}")
                            logger.info(f"   👉 샘플 값: {sample}")
                        else:
                            logger.info(f"   ⚠️ 빈 데이터 수신: {data}")
                        return
                except asyncio.TimeoutError:
                    logger.warning("   ⏰ 데이터 수신 시간 초과")
                    break
    except Exception as e: logger.error(f"   ❌ 실패: {e}")

async def main():
    logger.info("🕵️‍♂️ V2 데이터 구조 정밀 분석 시작 (멈춤 방지 적용됨)")
    
    await inspect_lighter()
    await inspect_extended()
    await inspect_pacifica() # 문제의 Pacifica를 마지막에 실행
    
    logger.info("\n🏁 검사 완료.")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass