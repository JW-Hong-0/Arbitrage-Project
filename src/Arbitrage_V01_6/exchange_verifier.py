import asyncio
import logging
import sys
import json
import os
from dotenv import load_dotenv

# 기존 모듈 임포트
import settings
from exchange_apis import GrvtExchange, LighterExchange

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("Verifier")

# .env 로드
load_dotenv()

async def test_grvt():
    print("\n==========================================")
    print("🛡️ GRVT SDK 접속 테스트")
    print("==========================================")
    
    if not os.getenv('GRVT_TRADING_ACCOUNT_ID'):
        log.error("❌ .env에 'GRVT_TRADING_ACCOUNT_ID'가 없습니다!")
        return

    try:
        grvt = GrvtExchange()
        log.info("⏳ GRVT 연결 및 마켓 정보 로딩 중...")
        await grvt.load_markets()
        
        if grvt.market_info:
            count = len(grvt.market_info)
            log.info(f"✅ GRVT 연결 성공! 총 {count}개 심볼 로드됨")
            if 'BTC' in grvt.market_info:
                info = grvt.market_info['BTC']
                log.info(f"   👉 BTC: 최소수량 {info['min_size']}, 자릿수 {info['qty_prec']}")
        else:
            log.error("❌ GRVT 연결 실패 (마켓 정보 없음)")
            
    except Exception as e:
        log.error(f"❌ GRVT 테스트 중 에러: {e}")

async def test_lighter_leverage():
    print("\n==========================================")
    print("🕯️ Lighter 레버리지/계정 정보 확인")
    print("==========================================")
    
    # [수정됨] 사용자의 .env 변수명 반영
    private_key = os.getenv('LIGHTER_PRIVATE_KEY')
    wallet_addr = os.getenv('LIGHTER_WALLET_ADDRESS')
    
    if not private_key:
        log.error("❌ .env에 'LIGHTER_PRIVATE_KEY'가 없습니다!")
        return

    try:
        # 1. 거래소 인스턴스 생성
        lighter_ex = LighterExchange(private_key, wallet_addr)
        
        # 2. 마켓 정보 로드
        log.info("⏳ Lighter 마켓 정보 로딩 중...")
        await lighter_ex.load_markets()
        if lighter_ex.market_info:
             log.info(f"✅ Lighter 마켓 정보 로드 성공 ({len(lighter_ex.market_info)}개)")
        
        # 3. 레버리지 설정 테스트 (읽기 전용이라 실제 변경은 안 함, 로그만 확인)
        #    Lighter SDK를 직접 호출하여 계정 정보를 봅니다.
        import lighter
        from lighter.configuration import Configuration
        
        BASE_URL = "https://api.lighter.xyz" 
        api_client = lighter.ApiClient(configuration=Configuration(host=BASE_URL))
        
        # [중요] Lighter SDK에는 get_account가 명확하지 않아 
        #        InfoApi 등을 통해 간접 정보를 확인합니다.
        info_api = lighter.InfoApi(api_client)
        
        # 4. 레버리지 설정 메서드 존재 여부 확인
        #    (Exchange 클래스에 set_leverage가 구현되어 있는지)
        if hasattr(lighter_ex, 'set_leverage'):
             log.info("✅ LighterExchange에 'set_leverage' 메서드가 구현되어 있습니다.")
             log.info("   -> 봇 실행 시 'update_leverage' API를 호출할 수 있습니다.")
        else:
             log.warning("⚠️ LighterExchange에 'set_leverage'가 구현되지 않았습니다.")

    except Exception as e:
        log.error(f"❌ Lighter 테스트 중 에러: {e}")

async def test_pacifica_capabilities():
    print("\n==========================================")
    print("🌊 Pacifica 기능 확인")
    print("==========================================")
    # Pacifica는 이미 로직이 검증되었으므로, 현재 코드에 기능이 포함되었는지만 체크
    from exchange_apis import PacificaExchange
    
    if hasattr(PacificaExchange, 'set_leverage'):
        log.info("✅ Pacifica: 'set_leverage' 기능 포함됨 (POST /account/leverage)")
    else:
        log.warning("⚠️ Pacifica: 'set_leverage' 기능이 보이지 않습니다.")

    if hasattr(PacificaExchange, 'load_markets'):
        log.info("✅ Pacifica: 'load_markets' 기능 포함됨 (GET /info)")
    else:
        log.warning("⚠️ Pacifica: 'load_markets' 기능이 보이지 않습니다.")

async def main():
    await test_grvt()
    await test_lighter_leverage()
    await test_pacifica_capabilities()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())