# lighter_tester.py
# (Lighter Exchange 웹소켓 테스트 - 메시지 구독 방식)

import asyncio
import logging
import json
import websockets

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)
logger = logging.getLogger("LighterTester")

# Lighter 메인넷 WS URL (SDK Configuration 참조)
# https://mainnet.zklighter.elliot.ai -> wss://mainnet.zklighter.elliot.ai/stream
WS_URL = "wss://mainnet.zklighter.elliot.ai/stream"

# 테스트할 마켓 ID 리스트 (0번부터 순서대로 테스트)
TEST_MARKET_IDS = [0, 1, 10] 

async def test_lighter_ws():
    logger.info(f"🔌 Lighter 연결 시도: {WS_URL}")
    
    try:
        async with websockets.connect(WS_URL) as ws:
            logger.info("✅ 연결 성공!")
            
            # 구독 요청 보내기
            for market_id in TEST_MARKET_IDS:
                sub_msg = {
                    "type": "subscribe",
                    "channel": f"order_book/{market_id}"
                }
                await ws.send(json.dumps(sub_msg))
                logger.info(f"📤 구독 요청: order_book/{market_id}")
            
            logger.info("📥 데이터 수신 대기 중...")
            
            while True:
                response = await ws.recv()
                data = json.loads(response)
                
                msg_type = data.get("type")
                
                if msg_type == "update/order_book":
                    # 오더북 업데이트 데이터
                    channel = data.get("channel")
                    bids = len(data.get("order_book", {}).get("bids", []))
                    asks = len(data.get("order_book", {}).get("asks", []))
                    logger.info(f"📊 [{channel}] 오더북 업데이트 (Bids:{bids}, Asks:{asks})")
                elif msg_type == "subscribed/order_book":
                    logger.info(f"🎉 구독 성공: {data.get('channel')}")
                elif msg_type == "ping":
                    # 핑 응답 (필수)
                    await ws.send(json.dumps({"type": "pong"}))
                    logger.info("🏓 Pong 전송")
                else:
                    logger.info(f"ℹ️ [Msg] {data}")

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_lighter_ws())
    except KeyboardInterrupt:
        logger.info("🛑 테스트 종료")