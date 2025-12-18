# grvt_tester.py
# (grvt-pysdk의 'test_grvt_ccxt_ws.py'를 기반으로 BBO 구독을 위해 수정)

import asyncio
import os
import signal
import sys
import traceback
import logging

# --- SDK 경로 설정 (중요) ---
# 이 파일이 프로젝트 루트의 'trader' 폴더에 있다고 가정
try:
    from pysdk.grvt_ccxt_env import GrvtEnv, GrvtWSEndpointType
    from pysdk.grvt_ccxt_logging_selector import logger # SDK의 기본 로거 사용
    from pysdk.grvt_ccxt_ws import GrvtCcxtWS
except ImportError as e:
    print(f"❌ GRVT SDK 임포트 실패: {e}")
    print("터미널에서 'pip install grvt-pysdk' 명령어를 실행하여 SDK를 설치했는지 확인하세요.")
    print("   (참고: 'python311'과 'python313' 등 여러 버전에 각각 설치해야 할 수 있습니다.)")
    sys.exit(1)
# -----------------------------


# --- [설정] ---
# .env 파일 또는 config/settings.py 기반으로 환경 설정
# settings.py의 'target_asset_lighter'와 동일한 심볼 사용
# (test_grvt_ccxt_ws.py 예제는 'BTC_USDT_Perp'를 사용)
TARGET_SYMBOL = "BTC_USDT_Perp" # 👈 ⭐️ "BTC_USDT_Perp" 또는 "BTC-PERP"

# settings.py의 'use_testnet' 값에 따라 환경 결정
# ⭐️ .env 파일에 'GRVT_ENV=mainnet' 또는 'GRVT_ENV=testnet'을 설정하는 것을 권장합니다.
# config/settings.py를 직접 임포트하는 대신, 예제와 동일하게 os.getenv를 사용
ENV_NAME = os.getenv("GRVT_ENV", "prod") # 👈 ⭐️ [수정] "mainnet"이 아닌 "prod"가 올바른 값입니다.
# -----------------

# 로깅 레벨 설정 (SDK 로거에 적용)
logger.setLevel(logging.INFO) #logger.setLevel(logging.DEBUG)


async def on_bbo_update(message: dict) -> None:
    """
    [규칙 1] 'book.s' (오더북 스냅샷) 메시지를 처리하여 BBO를 추출하는 콜백
    [수정] 실제 수신된 데이터 구조('feed' 키)에 맞게 파싱 로직 변경
    """
    logger.debug(f"Raw Message: {message}") # (디버깅용 - 이제 주석 처리해도 됩니다)
    
    # [수정] 'params' 대신 'stream'과 'feed' 키를 직접 파싱합니다.
    stream = message.get("stream")
    feed = message.get("feed")

    # 'v1.book.s' 스트림의 'feed' 데이터인지 확인
    if stream == "v1.book.s" and feed:
        try:
            bids = feed.get('bids', []) # 매수 호가 리스트
            asks = feed.get('asks', []) # 매도 호가 리스트

            if bids and asks:
                # L2 오더북의 첫 번째 항목이 BBO입니다.
                # [수정] 데이터가 리스트가 아닌 딕셔너리이므로 키로 접근
                best_bid = bids[0] # {'price': ..., 'size': ...}
                best_ask = asks[0] # {'price': ..., 'size': ...}
                
                bid_price = float(best_bid['price'])
                bid_size = float(best_bid['size'])
                ask_price = float(best_ask['price'])
                ask_size = float(best_ask['size'])
                
                # (성공!) 이제 이 부분이 출력될 것입니다.
                print(f"--- GRVT {TARGET_SYMBOL} (실시간 BBO) ---") 
                print(f"📈 BEST BID (매수): {bid_price:<10} (수량: {bid_size})")
                print(f"📉 BEST ASK (매도): {ask_price:<10} (수량: {ask_size})")
                print(f"📊 SPREAD: {ask_price - bid_price:.2f}\n")
        
        except Exception as e:
            logger.error(f"[BBO 처리 오류] {e}", exc_info=True)
            logger.debug(f"[오류 데이터] {message}")
            
    elif "result" in message:
        # 'subscribed to stream' 같은 확인 메시지
        logger.debug(f"[구독 확인 메시지] {message.get('result')}")
    else:
        logger.debug(f"[기타 메시지] {message}")


async def subscribe_bbo(loop) -> GrvtCcxtWS:
    """
    GRVT 웹소켓에 연결하고 BBO 관련 채널('book.s')만 구독합니다.
    """
    params = {
        # 공개 채널 구독에는 API 키가 필요하지 않습니다.
        "api_ws_version": os.getenv("GRVT_WS_STREAM_VERSION", "v1"),
    }
    env = GrvtEnv(ENV_NAME)

    logger.info(f"🔌 GRVT 웹소켓({ENV_NAME}) 연결 시도...")
    api = GrvtCcxtWS(env, loop, logger, parameters=params)
    await api.initialize()
    logger.info("✅ 웹소켓 연결 및 초기화 완료.")

    # BBO를 얻기 위해 'book.s' (L2 스냅샷) 채널 구독
    # (test_grvt_ccxt_ws.py의 pub_args_dict 참고)
    stream_to_subscribe = "book.s"
    stream_params = {"instrument": TARGET_SYMBOL}
    
    try:
        logger.info(f"Subscribing to {stream_to_subscribe} (Params: {stream_params})")
        await api.subscribe(
            stream=stream_to_subscribe,
            callback=on_bbo_update, # 👈 우리가 만든 BBO 콜백 지정
            ws_end_point_type=GrvtWSEndpointType.MARKET_DATA_RPC_FULL,
            params=stream_params,
        )
        logger.info(f"✅ 구독 요청 완료. 메시지 수신 대기 중... (Ctrl+C로 종료)")
        
    except Exception as e:
        logger.error(f"❌ 구독 실패: {e} {traceback.format_exc()}")
        await api.close() # 
        return None
        
    return api


async def shutdown(loop, test_api: GrvtCcxtWS) -> None:
    """
    (test_grvt_ccxt_ws.py에서 복사)
    리소스 정리 및 정상 종료
    """
    logger.info("🔌 종료 중...")
    if test_api:
        logger.info("GrvtCcxtWS 객체 삭제 중...")
        await test_api.close() # 👈 [수정] del 대신 SDK의 비동기 close 호출
        
    logger.info("모든 태스크 취소 중...")
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
    _ = [task.cancel() for task in tasks]
    logger.info(f"{len(tasks)}개 태스크 취소 요청")
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("✅ 종료 완료.")
    sys.exit(0)


# --- 메인 실행 ---
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    test_api = None
    try:
        test_api = loop.run_until_complete(subscribe_bbo(loop))
        if not test_api:
            logger.error("❌ 초기 구독에 실패하여 프로그램을 시작할 수 없습니다.")
            sys.exit(1)
            
        # [수정] 윈도우에서 지원하지 않는 add_signal_handler 블록을 삭제합니다.
        # (아래의 'except KeyboardInterrupt:' 블록이 윈도우에서 Ctrl+C를 처리합니다.)
        
        logger.info("✅ 윈도우 호환 모드로 실행. Ctrl+C로 종료하세요.")
        
        # (test_grvt_ccxt_ws.py에서 복사)
        # 프로그램이 계속 실행되도록 루프를 영원히 실행
        # (Ctrl+C를 누르면 이 줄에서 KeyboardInterrupt가 발생합니다)
        loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("... Ctrl+C 감지 ...")
        if test_api:
             loop.run_until_complete(shutdown(loop, test_api))
    finally:
        loop.close()
        logger.info("이벤트 루프 종료.")