# pacifica_tester.py
# (Pacifica 공식 예제 기반 테스트 코드)

import asyncio
import websockets
import json
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PacificaTester")

# Pacifica 공식 WS URL (메인넷)
# 참고: https://docs.pacifica.fi/developers/websocket-api
WS_URL = "wss://ws.pacifica.fi/ws" 

async def test_pacifica_ws():
    logger.info(f"🔌 Pacifica 웹소켓 연결 시도: {WS_URL}")
    
    try:
        async with websockets.connect(WS_URL, ping_interval=30) as websocket:
            logger.info("✅ 연결 성공!")
            
            # 구독 메시지 전송 (prices 채널)
            # 이 채널은 Mark Price, Index Price 등을 제공합니다.
            ws_message = {
                "method": "subscribe", 
                "params": {"source": "prices"}
            }
            await websocket.send(json.dumps(ws_message))
            logger.info(f"📤 구독 요청 전송: {ws_message}")
            
            logger.info("📥 데이터 수신 대기 중... (Ctrl+C로 종료)")
            
            # 메시지 수신 루프
            async for message in websocket:
                data = json.loads(message)
                
                # 데이터가 너무 길 수 있으므로, 보기 좋게 요약해서 출력
                if isinstance(data, dict) and data.get("type") == "prices":
                    logger.info(f"📊 [Price Data] {len(data.get('data', []))}개 심볼 데이터 수신")
                    # 첫 번째 데이터 샘플 출력
                    if data.get("data"):
                        logger.info(f"   👉 샘플: {data['data'][0]}")
                else:
                    logger.info(f"ℹ️ [Msg] {data}")

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_pacifica_ws())
    except KeyboardInterrupt:
        logger.info("🛑 테스트 종료")