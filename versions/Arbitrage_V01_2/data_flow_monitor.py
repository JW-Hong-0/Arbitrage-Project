import asyncio
import sys
import os
import time
import logging
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
    import settings
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange,
        ExtendedExchange, LighterExchange
    )
except ImportError as e:
    print(f"❌ 필수 모듈 로드 실패: {e}")
    sys.exit(1)

# 로깅 최소화
logging.basicConfig(level=logging.ERROR)

class DataFlowMonitor:
    def __init__(self):
        self.is_running = False
        self.exchanges = {
            'HL': HyperliquidExchange(os.getenv("HL_PRIVATE_KEY"), os.getenv("HL_ACCOUNT_ADDRESS")),
            'GRVT': GrvtExchange(os.getenv("GRVT_API_KEY"), os.getenv("GRVT_SECRET_KEY"), os.getenv("GRVT_TRADING_ACCOUNT_ID")),
            'PAC': PacificaExchange(os.getenv("PACIFICA_PRIVATE_KEY"), os.getenv("PACIFICA_ADDRESS")),
            'EXT': ExtendedExchange(os.getenv("EXTENDED_PRIVATE_KEY"), os.getenv("EXTENDED_ADDRESS")),
            'LTR': LighterExchange(os.getenv("LIGHTER_API_KEY"), os.getenv("LIGHTER_PUBLIC_KEY"))
        }
        
    # [핵심 수정] 빈 비동기 콜백 함수 정의
    async def _dummy_callback(self, data):
        pass

    async def _display_loop(self):
        print("Waiting for data stream...")
        await asyncio.sleep(5) # 초기 데이터 수집 대기
        
        while self.is_running:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"\n📊 데이터 정밀 모니터 (Bid/Ask Check) - {time.strftime('%H:%M:%S')}")
            print("=" * 120)
            print(f"{'Ticker':<10} | {'HL (Bid/Ask)':<20} | {'GRVT':<10} | {'PAC':<10} | {'EXT':<10} | {'LTR':<10} | {'Real Spread':<10}")
            print("-" * 120)
            
            target_coins = sorted(list(settings.TARGET_PAIRS_CONFIG.keys()))
            
            for ticker in target_coins:
                # 각 거래소 캐시에서 데이터 가져오기
                hl_data = self.exchanges['HL'].get_bbo(ticker)
                grvt_data = self.exchanges['GRVT'].get_bbo(ticker)
                pac_data = self.exchanges['PAC'].get_bbo(ticker)
                ext_data = self.exchanges['EXT'].get_bbo(ticker)
                ltr_data = self.exchanges['LTR'].get_bbo(ticker)
                
                # HL 데이터 포맷팅 (Bid/Ask 둘다 표시)
                if hl_data:
                    hl_str = f"{hl_data['bid']:.4g}/{hl_data['ask']:.4g}"
                else:
                    hl_str = "---"
                
                # 나머지 거래소는 Bid만 표시 (공간 절약)
                def fmt(d): return f"{d['bid']:.4g}" if d else "---"
                
                # 리얼 스프레드 계산 (Max Bid - Min Ask)
                all_data = [d for d in [hl_data, grvt_data, pac_data, ext_data, ltr_data] if d]
                spread_str = "0.00%"
                
                if len(all_data) >= 2:
                    # 매도(Short)할 곳: 비싸게 사주는 곳 (Max Bid)
                    max_bid = max(d['bid'] for d in all_data)
                    # 매수(Long)할 곳: 싸게 파는 곳 (Min Ask)
                    min_ask = min(d['ask'] for d in all_data)
                    
                    if min_ask > 0:
                        spread = ((max_bid - min_ask) / min_ask) * 100
                        spread_str = f"{spread:.2f}%"
                        if spread > 0.5: spread_str += " 🟢"

                print(f"{ticker:<10} | {hl_str:<20} | {fmt(grvt_data):<10} | {fmt(pac_data):<10} | {fmt(ext_data):<10} | {fmt(ltr_data):<10} | {spread_str}")

            await asyncio.sleep(1)

    async def run(self):
        self.is_running = True
        # [핵심 수정] lambda x: None 대신 async 함수(_dummy_callback) 전달
        tasks = [ex.start_ws(self._dummy_callback) for ex in self.exchanges.values()]
        tasks.append(self._display_loop())
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monitor = DataFlowMonitor()
    try:
        loop.run_until_complete(monitor.run())
    except KeyboardInterrupt:
        print("\nMonitor Stopped.")