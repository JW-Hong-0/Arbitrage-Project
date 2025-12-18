import asyncio
import sys
import os
import logging 
import time
from collections import defaultdict

# 기존 모듈 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
    import settings
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange, 
        ExtendedExchange, LighterExchange
    )
except ImportError as e:
    print(f"❌ 모듈 로드 실패: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("Tester")

class UniversalTester:
    def __init__(self):
        self.exchanges = {
            'HL': HyperliquidExchange(os.getenv("HL_PRIVATE_KEY"), os.getenv("HL_ACCOUNT_ADDRESS")),
            'GRVT': GrvtExchange(os.getenv("GRVT_API_KEY"), os.getenv("GRVT_SECRET_KEY"), os.getenv("GRVT_TRADING_ACCOUNT_ID")),
            'PAC': PacificaExchange(os.getenv("PACIFICA_PRIVATE_KEY"), os.getenv("PACIFICA_ADDRESS")),
            'EXT': ExtendedExchange(os.getenv("EXTENDED_PRIVATE_KEY"), os.getenv("EXTENDED_ADDRESS")),
            'LTR': LighterExchange(os.getenv("LIGHTER_API_KEY"), os.getenv("LIGHTER_PUBLIC_KEY"))
        }
        self.received = defaultdict(set) # { 'HL': {'BTC', 'ETH'}, ... }

    async def start(self):
        log.info("🧪 5대 거래소 통합 오더북 테스터 시작...")
        
        tasks = []
        for name, ex in self.exchanges.items():
            tasks.append(ex.start_ws(self._create_callback(name)))
            
        for t in tasks: asyncio.create_task(t)
        
        log.info("⏳ 30초간 데이터 수집 중... (화면을 지켜보세요)")
        
        for i in range(30):
            await asyncio.sleep(1)
            self._print_status()
            
        log.info("\n✅ 테스트 완료.")

    def _create_callback(self, ex_name):
        async def callback(bbo):
            self.received[ex_name].add(bbo['symbol'])
        return callback

    def _print_status(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\n📊 실시간 수신 현황 (타겟: {len(settings.TARGET_PAIRS_CONFIG)}개 코인)")
        print("-" * 40)
        for name in self.exchanges.keys():
            count = len(self.received[name])
            status = "🟢 정상" if count > 0 else "🔴 대기중..."
            print(f"{name:<5}: {count:>3}개 수신 중... [{status}]")
        print("-" * 40)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(UniversalTester().start()) # [수정] 메인 함수는 Universal