import asyncio
import logging
import sys
import os
import time
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("DUAL_TESTER")

try:
    from exchange_apis import HyperliquidExchange, GrvtExchange
except ImportError as e:
    log.error(f"❌ exchange_apis.py를 찾을 수 없거나 불러올 수 없습니다: {e}")
    sys.exit(1)

# === 테스트 설정 (여기만 수정하세요) ===
# 테스트할 수량 (최소 주문 수량 이상이어야 함)
TRADE_SIZE_BTC = 0.002  # 예: 약 $190
TRADE_SIZE_ETH = 0.06   # 예: 약 $200 (GRVT 최소단위 0.01 고려)

async def main():
    load_dotenv()
    log.info("🚀 [1단계] 듀얼 테스터 시작")

    # 1. 거래소 연결
    try:
        # API Key는 .env 파일에서 자동으로 로드됩니다.
        # Hyperliquid는 Private Key가 필요합니다.
        hl_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        if not hl_key:
            log.error("❌ .env에 HYPERLIQUID_PRIVATE_KEY가 없습니다.")
            return

        hl = HyperliquidExchange(private_key=hl_key)
        grvt = GrvtExchange() # 환경변수에서 키 로드
        
        log.info("🔌 거래소 객체 생성 완료")

    except Exception as e:
        log.error(f"❌ 초기화 실패: {e}")
        return

    # 2. 시장 데이터(자릿수) 로드 - 핵심!
    log.info("\n📥 [2단계] 시장 데이터(Precision) 동기화 중...")
    await asyncio.gather(
        hl.load_markets(),
        grvt.load_markets()
    )
    
    # 데이터 확인 로그
    log.info(f"   👉 HL BTC 설정: {hl.market_info.get('BTC', 'N/A')}")
    log.info(f"   👉 GRVT BTC 설정: {grvt.market_info.get('BTC', 'N/A')}")
    log.info(f"   👉 GRVT ETH 설정: {grvt.market_info.get('ETH', 'N/A')}")

    # 3. 진입 주문 (Hedge Position)
    # 시나리오: HL [BTC롱 / ETH숏] vs GRVT [BTC숏 / ETH롱]
    log.info("\n⚔️ [3단계] 포지션 진입 시도 (시장가)")
    log.info(f"   Plan: HL(Buy BTC, Sell ETH) vs GRVT(Sell BTC, Buy ETH)")

    tasks = []
    
    # Hyperliquid 주문 (Builder Code 포함됨)
    tasks.append(hl.place_market_order('BTC', 'BUY', TRADE_SIZE_BTC))
    tasks.append(hl.place_market_order('ETH', 'SELL', TRADE_SIZE_ETH))
    
    # GRVT 주문 (create_order 사용)
    # GRVT는 심볼명을 풀네임으로 변환하거나 내부적으로 처리함 (exchange_apis 로직 의존)
    tasks.append(grvt.place_market_order('BTC_USDT_Perp', 'SELL', TRADE_SIZE_BTC))
    tasks.append(grvt.place_market_order('ETH_USDT_Perp', 'BUY', TRADE_SIZE_ETH))

    # 주문 전송
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 결과 요약
    success_count = 0
    for i, res in enumerate(results):
        if isinstance(res, Exception) or res is None:
            log.error(f"   ❌ 주문 {i+1} 실패: {res}")
        else:
            success_count += 1
            # log.info(f"   ✅ 주문 {i+1} 성공: {res}") # 상세 로그 필요시 주석 해제

    log.info(f"   📨 주문 전송 완료 ({success_count}/4 성공)")

    if success_count < 4:
        log.warning("⚠️ 일부 주문이 실패했습니다. 포지션을 확인하세요.")

    # 4. 체결 대기 및 포지션 확인
    log.info("\n⏳ [4단계] 체결 확인 대기 (5초)...")
    await asyncio.sleep(5)

    # 포지션 조회 (간이 구현 - SDK 버전에 따라 다를 수 있음)
    # 검증을 위해 각 거래소의 잔고/포지션 조회 메서드 호출
    # (exchange_apis.py에 get_balance/positions가 구현되어 있다고 가정하지 않고 직접 구현하거나 생략)
    log.info("   👀 (수동 확인 권장) 거래소 웹사이트나 앱에서 포지션을 확인하세요.")

    # 5. 청산 (Close All)
    log.info("\n🧹 [5단계] 포지션 청산 (5초 뒤 실행)")
    await asyncio.sleep(5)
    
    close_tasks = []
    
    # 진입의 반대 주문
    # HL: Sell BTC, Buy ETH
    close_tasks.append(hl.place_market_order('BTC', 'SELL', TRADE_SIZE_BTC))
    close_tasks.append(hl.place_market_order('ETH', 'BUY', TRADE_SIZE_ETH))
    
    # GRVT: Buy BTC, Sell ETH
    close_tasks.append(grvt.place_market_order('BTC_USDT_Perp', 'BUY', TRADE_SIZE_BTC))
    close_tasks.append(grvt.place_market_order('ETH_USDT_Perp', 'SELL', TRADE_SIZE_ETH))

    close_results = await asyncio.gather(*close_tasks, return_exceptions=True)
    log.info("🏁 청산 주문 전송 완료")
    
    for res in close_results:
        if isinstance(res, Exception) or res is None:
            log.error(f"   ❌ 청산 실패 항목 있음: {res}")

    log.info("\n✅ 테스트 종료")

if __name__ == "__main__":
    asyncio.run(main())