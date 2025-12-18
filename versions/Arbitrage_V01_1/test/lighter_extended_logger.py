import asyncio
import websockets
import json
import ssl
import logging
import sys

# 설정에서 ID 하나만 빌려옴 (예: BTC=1, BTC-USD)
LIGHTER_TEST_ID = 1 
EXTENDED_TEST_SYM = "BTC-USD"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("Verifier")

async def check_lighter():
    logger.info(f"⚪ [Lighter] ID {LIGHTER_TEST_ID} (BTC) 구독 테스트...")
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    try:
        async with websockets.connect(url, extra_headers={"User-Agent": "Mozilla/5.0"}) as ws:
            await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{LIGHTER_TEST_ID}"}))
            for i in range(3):
                msg = await ws.recv()
                logger.info(f"   📩 수신: {msg[:150]}...")
    except Exception as e: logger.error(f"   ❌ 실패: {e}")

async def check_extended():
    logger.info(f"🟣 [Extended] {EXTENDED_TEST_SYM} 구독 테스트...")
    url = f"wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks/{EXTENDED_TEST_SYM}"
    ssl_ctx = ssl.create_default_context(); ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        async with websockets.connect(url, ssl=ssl_ctx, extra_headers={"User-Agent": "Mozilla/5.0"}) as ws:
            msg = await ws.recv()
            logger.info(f"   📩 수신: {msg[:150]}...")
    except Exception as e: logger.error(f"   ❌ 실패: {e}")

async def main():
    await check_lighter()
    await check_extended()

if __name__ == "__main__":
    if sys.platform.startswith('win'): asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())