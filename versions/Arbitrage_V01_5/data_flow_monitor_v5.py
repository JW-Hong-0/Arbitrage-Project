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

# 로깅 최소화 (화면 출력 방해 금지)
logging.basicConfig(level=logging.ERROR)

class DataFlowMonitor:
    def __init__(self):
        self.is_running = False
        print("🔌 거래소 연결 초기화 중...")
        
        self.exchanges = {}
        
        # 1. Hyperliquid
        if os.getenv('HYPERLIQUID_PRIVATE_KEY'):
            self.exchanges['HL'] = HyperliquidExchange(os.getenv('HYPERLIQUID_PRIVATE_KEY'))
            
        # 2. GRVT
        if os.getenv('GRVT_API_KEY'):
            self.exchanges['GRVT'] = GrvtExchange()
            
        # 3. Pacifica
        if os.getenv('PACIFICA_MAIN_ADDRESS'):
            self.exchanges['PAC'] = PacificaExchange(
                os.getenv('PACIFICA_MAIN_ADDRESS'), 
                os.getenv('PACIFICA_AGENT_PRIVATE_KEY')
            )
            
        # 4. Extended
        if os.getenv('EXTENDED_API_KEY'):
            self.exchanges['EXT'] = ExtendedExchange(
                os.getenv('EXTENDED_PRIVATE_KEY'), 
                os.getenv('EXTENDED_PUBLIC_KEY'),
                os.getenv('EXTENDED_API_KEY'), 
                os.getenv('EXTENDED_VAULT')
            )
            
        # 5. Lighter
        if os.getenv('LIGHTER_PRIVATE_KEY'):
            self.exchanges['LTR'] = LighterExchange(
                os.getenv('LIGHTER_PRIVATE_KEY'), 
                os.getenv('LIGHTER_WALLET_ADDRESS')
            )

    # [핵심] 빈 비동기 콜백 함수 (데이터는 내부 캐시에 쌓임)
    async def _dummy_callback(self, data):
        pass

    async def _display_loop(self):
        print("⏳ 데이터 수신 대기 중... (10초)")
        
        # 마켓 데이터 로드 (필수)
        for name, ex in self.exchanges.items():
            print(f"   └ {name} 마켓 정보 로딩...")
            await ex.load_markets()
            
        await asyncio.sleep(5) 
        
        while self.is_running:
            # 화면 클리어 (Windows/Linux/Mac 호환)
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print(f"\n📊 [V01_5] 실시간 데이터 모니터 - {time.strftime('%H:%M:%S')}")
            print("=" * 100)
            print(f"{'Ticker':<8} | {'HL':<12} | {'GRVT':<10} | {'PAC':<10} | {'EXT':<10} | {'LTR':<10} | {'Spread'}")
            print("-" * 100)
            
            # Settings에 있는 티커만 모니터링
            target_coins = sorted(list(settings.TARGET_PAIRS_CONFIG.keys()))
            
            for ticker in target_coins:
                # 각 거래소 캐시에서 데이터 가져오기
                hl_data = self.exchanges.get('HL', {}).get_bbo(ticker) if 'HL' in self.exchanges else None
                grvt_data = self.exchanges.get('GRVT', {}).get_bbo(ticker) if 'GRVT' in self.exchanges else None
                pac_data = self.exchanges.get('PAC', {}).get_bbo(ticker) if 'PAC' in self.exchanges else None
                ext_data = self.exchanges.get('EXT', {}).get_bbo(ticker) if 'EXT' in self.exchanges else None
                ltr_data = self.exchanges.get('LTR', {}).get_bbo(ticker) if 'LTR' in self.exchanges else None
                
                # 데이터 포맷팅 함수
                def fmt(d): 
                    if d and d['bid'] > 0:
                        return f"{d['bid']:.4g}"
                    return "---"
                
                # 리얼 스프레드 계산
                all_data = [d for d in [hl_data, grvt_data, pac_data, ext_data, ltr_data] if d and d['bid'] > 0]
                spread_str = ""
                
                if len(all_data) >= 2:
                    max_bid = max(d['bid'] for d in all_data)
                    min_ask = min(d['ask'] for d in all_data if d['ask'] > 0)
                    
                    if min_ask > 0:
                        spread = ((max_bid - min_ask) / min_ask) * 100
                        spread_str = f"{spread:.2f}%"
                        if spread > 0.1: spread_str += " ✨"

                # 출력
                print(f"{ticker:<8} | {fmt(hl_data):<12} | {fmt(grvt_data):<10} | {fmt(pac_data):<10} | {fmt(ext_data):<10} | {fmt(ltr_data):<10} | {spread_str}")

            print("=" * 100)
            print("Usage: Ctrl+C to stop")
            await asyncio.sleep(1)

    async def run(self):
        self.is_running = True
        tasks = []
        
        # 각 거래소 웹소켓 시작
        for name, ex in self.exchanges.items():
            tasks.append(asyncio.create_task(ex.start_ws(self._dummy_callback)))
            
        # 모니터링 루프 시작
        tasks.append(asyncio.create_task(self._display_loop()))
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for ex in self.exchanges.values():
                await ex.close()

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monitor = DataFlowMonitor()
    try:
        loop.run_until_complete(monitor.run())
    except KeyboardInterrupt:
        monitor.is_running = False
        print("\n🛑 모니터링 종료.")