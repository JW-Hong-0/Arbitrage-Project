import asyncio
import websockets
import json
import logging
import ssl
import sys

# 로깅 설정 (모든 내용을 다 찍도록 설정)
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("Sniffer")

# 봇 차단 방지용 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://app.extended.exchange" # Extended용 Origin 추정
}

async def sniff_extended():
    """Extended: URL 접속 방식과 메시지 구독 방식 둘 다 시도"""
    logger.info("\n🟣 [Extended] 정밀 진단 시작...")
    
    # 시도 1: URL에 심볼을 넣어서 접속하는 방식 (SDK 스타일)
    # BTC-USD, BTC-USD-PERP, BTC_USD 등 다양한 패턴 시도
    symbols = ["BTC-USD", "ETH-USD"] 
    base_url = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    for sym in symbols:
        url = f"{base_url}/{sym}"
        logger.info(f"   👉 접속 시도: {url}")
        
        try:
            async with websockets.connect(url, ssl=ssl_ctx, extra_headers=HEADERS, open_timeout=5) as ws:
                logger.info(f"   ✅ 연결 성공! ({sym}) -> 데이터 대기 중...")
                
                # 5초간 데이터가 오는지 확인
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    logger.info(f"   🎉 [Extended RAW Data] {msg[:200]}...") # 너무 길면 자름
                    return # 성공하면 종료
                except asyncio.TimeoutError:
                    logger.warning("   ⏰ 연결은 됐는데 데이터가 안 옴 (Timeout)")
        except Exception as e:
            logger.error(f"   ❌ 연결 실패: {e}")

async def sniff_lighter():
    """Lighter: ID 구독 후 오는 메시지 전수 조사"""
    logger.info("\n⚪ [Lighter] 정밀 진단 시작...")
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, open_timeout=5) as ws:
            logger.info(f"   ✅ 서버 연결 성공! 구독 요청 전송 중...")
            
            # ID 0, 1, 10, 100 무차별 구독 요청
            ids = [0, 1, 2, 10]
            for i in ids:
                payload = json.dumps({"type": "subscribe", "channel": f"order_book/{i}"})
                await ws.send(payload)
                logger.info(f"   📤 보냄: {payload}")
            
            # 응답 확인 (최대 5개)
            logger.info("   📥 응답 대기 중...")
            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    logger.info(f"   🎉 [Lighter RAW Data] {msg}")
                    
                    # 핑이면 퐁 해주기 (연결 유지 테스트)
                    data = json.loads(msg)
                    if data.get('type') == 'ping':
                        await ws.send(json.dumps({"type": "pong"}))
                        logger.info("   🏓 Pong 전송")
                except asyncio.TimeoutError:
                    logger.warning("   ⏰ 더 이상 데이터가 안 옴")
                    break
                    
    except Exception as e:
        logger.error(f"   ❌ Lighter 연결 실패: {e}")

async def main():
    print("="*60)
    print("🕵️‍♂️ 거래소 프로토콜 스니퍼 (Raw Data Sniffer)")
    print("="*60)
    
    # 두 거래소 동시 실행 말고 순차 실행으로 로그 섞임 방지
    await sniff_extended()
    print("-" * 60)
    await sniff_lighter()
    
    print("\n" + "="*60)
    print("🏁 진단 완료. 이 로그를 보여주세요.")
    print("="*60)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())