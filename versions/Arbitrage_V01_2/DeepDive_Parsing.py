import asyncio
import websockets
import json
import ssl
import logging
import sys

# 윈도우 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger("DeepDive")

HEADERS = {"User-Agent": "Mozilla/5.0"}

async def capture_pacifica():
    logger.info("🟢 [Pacifica] 전체 데이터 캡처 중...")
    url = "wss://ws.pacifica.fi/ws"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, open_timeout=10) as ws:
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            
            # 데이터 올 때까지 대기 (최대 3개 메시지)
            for _ in range(3):
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                
                if data.get("channel") == "prices":
                    # 파일로 저장
                    with open("pacifica_raw.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    logger.info(f"   ✅ pacifica_raw.json 저장 완료! ({len(data.get('data', []))}개 코인)")
                    return
    except Exception as e:
        logger.error(f"   ❌ Pacifica 실패: {e}")

async def capture_extended_list():
    logger.info("🟣 [Extended] 지원 심볼 전수 조사 (무식하게 찌르기)...")
    # Extended는 전체 목록 API가 없으므로, 주요 코인 20개만 샘플링해서 이름 규칙 확인
    targets = ["BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "SUI", "ARB", "WLD", "ORDI"]
    patterns = ["-USD", "-USDC", "_USD", "USD"] # 가능한 접미사 패턴
    
    found = {}
    url_base = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    for t in targets:
        for p in patterns:
            sym = f"{t}{p}"
            try:
                async with websockets.connect(f"{url_base}/{sym}", ssl=ssl_ctx, open_timeout=1.0) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=1.0)
                    found[t] = sym
                    logger.info(f"   ✅ 발견: {sym}")
                    break # 찾았으면 다음 코인으로
            except: pass
            
    with open("extended_found.json", "w", encoding="utf-8") as f:
        json.dump(found, f, indent=4)
    logger.info("   ✅ extended_found.json 저장 완료")

async def main():
    await capture_pacifica()
    await capture_extended_list()

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())