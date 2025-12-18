import asyncio
import websockets
import json
import ssl
import logging
import sys

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("DeepDive")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://app.lighter.xyz" # Origin 헤더 추가 (중요할 수 있음)
}

async def test_lighter_deep_dive():
    """Lighter: Symbol로 구독 시도 & 오는 데이터 전수 조사"""
    logger.info("\n⚪ [Lighter] 심층 분석 시작...")
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS) as ws:
            logger.info("   ✅ Lighter 연결 성공!")
            
            # 테스트 1: ID로 구독 (기존 방식)
            await ws.send(json.dumps({"type": "subscribe", "channel": "order_book/1"}))
            logger.info("   📤 ID 구독 요청: order_book/1 (BTC 추정)")
            
            # 테스트 2: Symbol로 구독 시도 (혹시 되나?)
            await ws.send(json.dumps({"type": "subscribe", "channel": "order_book/BTC-USDC"}))
            logger.info("   📤 Symbol 구독 요청: order_book/BTC-USDC (테스트)")
            
            # 응답 확인 (5개만)
            for i in range(5):
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                logger.info(f"   📩 수신[{i}]: {msg}")
                
    except Exception as e:
        logger.error(f"   ❌ Lighter 실패: {e}")

async def test_extended_deep_dive():
    """Extended: 웹소켓 연결 후 메시지 구조 확인"""
    logger.info("\n🟣 [Extended] 심층 분석 시작...")
    # URL 후보군
    urls = [
        "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks/BTC-USD",
        "wss://api.starknet.extended.exchange/v1/stream/orderbooks/BTC-USD"
    ]
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    for url in urls:
        logger.info(f"   👉 접속 시도: {url}")
        try:
            async with websockets.connect(url, ssl=ssl_ctx, extra_headers=HEADERS) as ws:
                logger.info("   ✅ 연결 성공! 데이터 대기...")
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                logger.info(f"   📩 첫 번째 메시지: {msg[:200]}...") # 너무 길면 자름
                return
        except Exception as e:
            logger.warning(f"   ⚠️ 실패: {e}")

async def test_pacifica_deep_dive():
    """Pacifica: 데이터 구조 재확인"""
    logger.info("\n🔵 [Pacifica] 심층 분석 시작...")
    url = "wss://ws.pacifica.fi/ws"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, ping_interval=20) as ws:
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            logger.info("   📤 전체 시세 구독 요청")
            
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            logger.info(f"   📩 수신: {msg[:200]}...")
    except Exception as e:
        logger.error(f"   ❌ Pacifica 실패: {e}")

async def main():
    await test_lighter_deep_dive()
    await test_extended_deep_dive()
    await test_pacifica_deep_dive()
    logger.info("\n🏁 테스트 종료.")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())