# hyperliquid_sdk_tester.py
# (SDK의 'examples/basic_ws.py'를 기반으로 BBO 구독을 위해 수정)

import asyncio
import logging
import sys
import pprint
import os

# --- SDK 경로 설정 (중요) ---
# 이 파일이 프로젝트 루트의 'trader' 폴더에 있다고 가정
try:
    # 'hyperliquid' SDK가 설치된 경우
    from hyperliquid.info import Info
    from hyperliquid.websocket_manager import WebsocketManager
except ImportError:
    # SDK가 설치되지 않고, 프로젝트에 포함된 경우
    # (exchange_apis.py의 경로 설정을 참고)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SDK_PATH = os.path.join(PROJECT_ROOT, "hyperliquid-dex", "hyperliquid-python-sdk", "hyperliquid-python-sdk-ea8421347feaa2b21f2c8658af67e9adbf876df0")
    
    if SDK_PATH not in sys.path:
        sys.path.insert(0, SDK_PATH)
        
    # 'hyperliquid' 패키지 경로 추가 (SDK 구조에 따라)
    HL_PKG_PATH = os.path.dirname(SDK_PATH) # hyperliquid-python-sdk-ea84...의 부모
    if HL_PKG_PATH not in sys.path:
        sys.path.insert(0, HL_PKG_PATH)

    try:
        from hyperliquid.info import Info
        from hyperliquid.websocket_manager import WebsocketManager
    except ImportError as e:
        print(f"❌ SDK 경로 설정 실패: {e}")
        print("프로젝트 구조를 확인하거나 'pip install hyperliquid-python-sdk'를 실행하세요.")
        sys.exit(1)
# -----------------------------


# --- [설정] ---
# .env 또는 config 파일에서 가져오는 것을 권장
HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz" 
ASSET_TO_SUBSCRIBE = "ETH"
# -----------------

# 로깅 설정
logging.basicConfig(level=logging.DEBUG) 
log = logging.getLogger(__name__)

def on_message_bbo(message: dict):
    """
    [규칙 1] BBO (Best Bid/Ask) 메시지를 처리하는 콜백 함수
    (Info.subscribe는 메시지 1개만 인자로 전달합니다)
    """
    
    # --- 🐞 [디버깅 코드] ---
    # (이제 원인을 찾았으니 이 줄은 삭제하거나 주석 처리해도 됩니다)
    # print(f"\n[DEBUG] 📩 Raw Message Received: {message}\n")
    # -----------------------------

    channel = message.get("channel")
    data = message.get("data")

    if channel == "bbo" and data:
        try:
            # --- [핵심 수정] ---
            # 'data' 키 내부의 'bbo' 리스트를 직접 가져옵니다.
            bbo_list = data.get("bbo", []) 
            
            # 리스트에 [Bid, Ask] 2개의 항목이 있는지 확인합니다.
            if bbo_list and len(bbo_list) == 2:
                best_bid = bbo_list[0] # 0번째 항목이 Best Bid
                best_ask = bbo_list[1] # 1번째 항목이 Best Ask
            # ---------------------
            
                bid_price = float(best_bid['px'])
                bid_size = float(best_bid['sz'])
                ask_price = float(best_ask['px'])
                ask_size = float(best_ask['sz'])
                
                # (성공!) 이제 이 부분이 출력될 것입니다.
                print(f"--- {ASSET_TO_SUBSCRIBE.upper()}/USD (실시간 BBO) ---") 
                print(f"📈 BEST BID (매수): {bid_price:<10} (수량: {bid_size})")
                print(f"📉 BEST ASK (매도): {ask_price:<10} (수량: {ask_size})")
                print(f"📊 SPREAD: {ask_price - bid_price:.2f}\n")
        
        except Exception as e:
            log.error(f"[BBO 처리 오류] {e}", exc_info=True)
            log.debug(f"[오류 데이터] {message}")

    elif channel == "pong":
        log.info("<<< (Pong) 수신 (SDK가 자동 관리 중)")
    
    elif channel == "subscriptions":
        # DEBUG 레벨에서는 이것도 보입니다.
        log.debug(f"[구독 확인] {data}")
        
    else:
        log.debug(f"[기타 메시지] {message}")


async def main():
    """
    SDK의 Info 클래스와 WebsocketManager를 사용하여 BBO를 구독합니다.
    """
    
    # 1. Info 객체 생성 (메인넷 API URL 사용)
    # [수정] 이 단계에서 Info 객체는 내부적으로
    # 'ws_manager'를 생성하고 *자동으로* 백그라운드 스레드에서 시작합니다.
    log.info("Info 객체 생성 및 SDK 웹소켓 스레드 자동 시작...")
    info = Info(HYPERLIQUID_API_URL, skip_ws=False) # (지난번 수정하신 API URL 사용)
    log.info("✅ Info 객체 생성 완료.")
    
    # 2. [삭제] 'await info.websocket_manager.start()' 줄 삭제
    # (1번에서 이미 자동으로 시작되었습니다.)

    log.info(f"🔌 {ASSET_TO_SUBSCRIBE} 'bbo' 구독 요청...")

    # 3. "bbo" 채널 구독
    subscription_request = {
        "type": "bbo",
        "coin": ASSET_TO_SUBSCRIBE
    }
    
    # [수정] 'await' 삭제
    # info.subscribe는 비동기 함수(async def)가 아니므로 await를 사용하지 않습니다.
    info.subscribe(subscription_request, on_message_bbo)

    log.info(f"✅ 구독 요청 완료. 메시지 수신 대기 중... (Ctrl+C로 종료)")

    # 4. 프로그램이 종료되지 않도록 무한 대기
    #    (백그라운드에서 SDK의 *스레드*가 메시지를 수신하고 콜백을 호출)
    try:
        while True:
            await asyncio.sleep(3600) # (이 부분은 동일)
    except asyncio.CancelledError:
        log.info("... 대기 작업 취소됨")
    finally:
        # 5. 종료 시 웹소켓 연결 정리
        log.info("🔌 웹소켓 연결 종료 중...")
        
        # [수정] 올바른 속성 이름('ws_manager')을 사용하고,
        # stop() 메서드 역시 동기 함수이므로 'await'를 사용하지 않습니다.
        if info.ws_manager:
            info.ws_manager.stop()
            
        log.info("✅ 연결 종료 완료")


# --- 메인 실행 ---
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 프로그램 종료")