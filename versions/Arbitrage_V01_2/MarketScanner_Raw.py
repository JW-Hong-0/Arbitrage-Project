import asyncio
import websockets
import json
import ssl
import sys
import os
import logging

# 윈도우 인코딩 호환 설정
sys.stdout.reconfigure(encoding='utf-8')

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("RawSniffer")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================================================
# 1. Hyperliquid (BTC Raw Data)
# =========================================================
async def sniff_hyperliquid():
    logger.info("\n🔵 [1/5] Hyperliquid 접속 시도...")
    url = "wss://api.hyperliquid.xyz/ws"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS) as ws:
            # 구독 메시지 전송 (L2 Book - BTC)
            req = {"method": "subscribe", "subscription": {"type": "l2Book", "coin": "BTC"}}
            await ws.send(json.dumps(req))
            logger.info("   >> 구독 요청 전송: BTC l2Book")
            
            # 메시지 3개 수신
            for i in range(3):
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                # 너무 길면 자름
                preview = msg[:200] + "..." if len(msg) > 200 else msg
                print(f"   [HL RAW #{i+1}] {preview}")
                
            logger.info("   ✅ Hyperliquid 수신 성공")
    except Exception as e:
        logger.error(f"   ❌ Hyperliquid 실패: {e}")

# =========================================================
# 2. Pacifica (Raw Data - 구독 확인 건너뛰기)
# =========================================================
async def sniff_pacifica():
    logger.info("\n🟢 [2/5] Pacifica 접속 시도 (대기시간 20초)...")
    url = "wss://ws.pacifica.fi/ws"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, open_timeout=10) as ws:
            req = {"method": "subscribe", "params": {"source": "prices"}}
            await ws.send(json.dumps(req))
            logger.info("   >> 구독 요청 전송: prices")
            
            received_count = 0
            # 최대 5번 시도 (첫번째는 ACK일 수 있음)
            start_t = asyncio.get_event_loop().time()
            
            while received_count < 2 and (asyncio.get_event_loop().time() - start_t < 20):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(msg)
                    
                    # 그냥 다 출력해봄
                    preview = str(msg)[:250] + "..." if len(msg) > 250 else msg
                    print(f"   [PAC RAW] {preview}")
                    
                    # 'payload'가 있는 진짜 데이터인지 체크 (로그용)
                    if "payload" in data:
                        logger.info("   => ✨ 유효 데이터(Payload) 감지됨!")
                    
                    received_count += 1
                except asyncio.TimeoutError:
                    logger.info("   ... 데이터 기다리는 중 ...")
                    # 핑 보내기 (연결 유지)
                    try: await ws.send(json.dumps({"method": "ping"}))
                    except: pass
            
            if received_count > 0:
                logger.info("   ✅ Pacifica 수신 성공")
            else:
                logger.warning("   ⚠️ Pacifica: 데이터가 안 옴 (장 마감 시간? 거래량 부족?)")
                
    except Exception as e:
        logger.error(f"   ❌ Pacifica 실패: {e}")

# =========================================================
# 3. Lighter (BTC Raw Data)
# =========================================================
async def sniff_lighter():
    logger.info("\n⚪ [3/5] Lighter 접속 시도...")
    url = "wss://mainnet.zklighter.elliot.ai/stream"
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS) as ws:
            # ID 1 (BTC 추정) 구독
            req = {"type": "subscribe", "channel": "order_book/1"}
            await ws.send(json.dumps(req))
            logger.info("   >> 구독 요청 전송: order_book/1")
            
            for i in range(2):
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                preview = msg[:200] + "..." if len(msg) > 200 else msg
                print(f"   [LTR RAW #{i+1}] {preview}")
                
            logger.info("   ✅ Lighter 수신 성공")
    except Exception as e:
        logger.error(f"   ❌ Lighter 실패: {e}")

# =========================================================
# 4. Extended (BTC-USD Raw Data)
# =========================================================
async def sniff_extended():
    logger.info("\n🟣 [4/5] Extended 접속 시도...")
    # BTC-USD 직접 접속
    url = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks/BTC-USD"
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    try:
        async with websockets.connect(url, ssl=ssl_ctx) as ws:
            logger.info("   >> BTC-USD 스트림 연결됨")
            
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            preview = msg[:200] + "..." if len(msg) > 200 else msg
            print(f"   [EXT RAW] {preview}")
            
            logger.info("   ✅ Extended 수신 성공")
    except Exception as e:
        logger.error(f"   ❌ Extended 실패: {e}")

# =========================================================
# 5. GRVT (SDK 활용 시도)
# =========================================================
async def sniff_grvt():
    logger.info("\n⚫ [5/5] GRVT 접속 시도 (with Settings)...")
    
    # 1. settings.py 로드 시도
    try:
        import settings
        api_key = os.getenv("GRVT_API_KEY")
        if not api_key:
            logger.warning("   ⚠️ GRVT_API_KEY가 환경변수에 없습니다. 스킵합니다.")
            return
    except ImportError:
        logger.warning("   ⚠️ settings.py를 찾을 수 없습니다.")
        return

    # 2. exchange_apis.py의 GrvtExchange 활용
    # 직접 구현은 복잡하므로 기존 모듈을 '도구'로 사용
    try:
        # 경로 문제 해결을 위해 현재 폴더를 sys.path에 추가
        sys.path.append(os.getcwd())
        from exchange_apis import GrvtExchange
        
        # 콜백 함수 정의 (데이터 들어오면 출력)
        async def raw_callback(data):
            # 딕셔너리로 가공된 데이터지만, 들어왔다는 것 자체가 중요
            print(f"   [GRVT DATA] {str(data)[:200]}...")
            
        # 객체 생성
        grvt = GrvtExchange(
            os.getenv("GRVT_API_KEY"),
            os.getenv("GRVT_SECRET_KEY"),
            os.getenv("GRVT_TRADING_ACCOUNT_ID")
        )
        
        # 웹소켓 실행 (5초간만)
        logger.info("   >> GRVT SDK 시작 (5초간 실행)...")
        
        # start_ws는 무한루프이므로, 타임아웃을 걸어서 강제 종료 시켜야 함
        # 또는 background task로 실행
        task = asyncio.create_task(grvt.start_ws(raw_callback))
        
        await asyncio.sleep(5)
        
        # 강제 종료
        grvt.ws_running = False
        task.cancel()
        logger.info("   ✅ GRVT 테스트 종료")
        
    except ImportError:
        logger.warning("   ⚠️ exchange_apis.py 또는 pysdk 로드 실패 (파일 경로 확인)")
    except Exception as e:
        logger.error(f"   ❌ GRVT 연결 중 에러: {e}")

# =========================================================
# 메인 실행
# =========================================================
async def main():
    print("="*60)
    print(" 🕵️‍♂️ 거래소 Raw Data Sniffer (데이터 검증용)")
    print("="*60)
    
    await sniff_hyperliquid()
    await sniff_pacifica()
    await sniff_lighter()
    await sniff_extended()
    await sniff_grvt()
    
    print("\n" + "="*60)
    print(" [진단 완료] 위 로그의 RAW 데이터를 확인하세요.")
    print("="*60)

if __name__ == "__main__":
    try:
        # .env 로드 시도
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except: pass
        
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass