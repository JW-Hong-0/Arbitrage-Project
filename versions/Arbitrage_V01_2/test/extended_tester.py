# extended_tester.py
# (Extended Exchange 웹소켓 테스트 - URL 경로 구독 방식)

import asyncio
import logging
import json
import websockets
import ssl

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)
logger = logging.getLogger("ExtendedTester")

# Extended 메인넷 스트림 URL
# SDK 분석 결과: wss://api.starknet.extended.exchange/stream.extended.exchange/v1
BASE_WS_URL = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1"

# 테스트할 마켓 (심볼)
# 주의: Extended는 심볼 형식이 'ETH-USD-PERP' 또는 'ETH-USD' 일 수 있습니다.
# SDK 예제 코드를 보면 'ETH-USD-PERP' 형식을 사용하는 것으로 추정됩니다.
MARKET_SYMBOL = "ETH-USD"

async def test_extended_ws():
    # 구독할 URL 완성
    ws_url = f"{BASE_WS_URL}/orderbooks/{MARKET_SYMBOL}"
    logger.info(f"🔌 Extended 연결 시도: {ws_url}")
    
    # SSL 컨텍스트 설정 (인증서 오류 방지)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        async with websockets.connect(ws_url, ssl=ssl_context) as ws:
            logger.info("✅ 연결 성공! (데이터 수신 대기 중...)")
            
            while True:
                response = await ws.recv()
                data = json.loads(response)
                
                # 데이터 타입 확인
                # Extended는 보통 'snapshot' 또는 'update' 타입을 보냄
                logger.info(f"📥 수신 데이터: {str(data)[:200]}...") # 너무 길면 자름

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_extended_ws())
    except KeyboardInterrupt:
        logger.info("🛑 테스트 종료")