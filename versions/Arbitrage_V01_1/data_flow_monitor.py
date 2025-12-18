import asyncio
import sys
import os
import time
from typing import Dict, List, Any
from collections import defaultdict
import logging

# --- 필수 임포트 ---
# [수정] NameError 해결을 위해 로거 변수를 log로 통일
from typing import List, Dict 

# 로깅 설정 (CMD 화면에만 깔끔하게 출력)
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("DataFlowMonitor")
log.setLevel(logging.INFO)

# 기존 모듈 로드
try:
    from arbitrage_bot import ArbitrageBot
    import settings
    from exchange_apis import Exchange
except ImportError as e:
    print(f"❌ 필수 모듈 로드 실패 (settings, arbitrage_bot 등): {e}")
    sys.exit(1)

# =========================================================================
# 💡 핵심: ArbitrageBot을 상속받아 데이터만 읽어옵니다.
# =========================================================================

class DataFlowMonitor(ArbitrageBot):
    def __init__(self, loop):
        super().__init__(loop)
        self.all_exchanges = list(self.exchanges.keys())
        self.is_running = True
        
    async def start_monitoring(self):
        log.info("📊 5대 거래소 실시간 데이터 크로스 체크 시작 (Raw Price View)")
        
        # 1. 웹소켓 연결 (Data Ingestion 시작)
        await self._connect_and_subscribe()
        
        # 2. 실시간 출력 루프 시작
        await self._realtime_output_loop()

    # 오버라이드: 계산 및 트레이딩 로직을 건너뛰도록 정의
    async def _on_market_update(self, bbo_data: Dict):
        pass 
        
    async def _realtime_output_loop(self):
        """0.5초마다 출력 갱신"""
        while True:
            # 1. 모든 티커 데이터 수집 및 계산
            table_data = self._get_current_prices()
            
            # 2. 출력
            self._print_status(table_data)
            
            await asyncio.sleep(0.5)

    def _get_current_prices(self) -> List[Dict]:
        """현재 BBO 캐시 상태를 종합하여 테이블 데이터로 반환"""
        table_data = []
        current_time = time.time()
        VALID_WINDOW = 3600.0 # 1시간 유효기간
        
        for ticker in list(settings.TARGET_PAIRS_CONFIG.keys()):
            row = {'Symbol': ticker, 'Prices': []}
            
            # 5개 거래소 캐시 조회
            for ex_name in self.all_exchanges:
                exchange: Exchange = self.exchanges[ex_name]
                bbo = exchange.get_bbo(ticker)
                
                price_bid = bbo.get('bid', 0.0) if bbo else 0.0
                data_time = bbo.get('timestamp', 0)
                
                if price_bid > 0 and (current_time - data_time < VALID_WINDOW):
                    # 가격은 Bid로 통일하여 사용
                    row[ex_name.upper()] = price_bid 
                    row['Prices'].append(price_bid)
                else:
                    row[ex_name.upper()] = '---'

            # 스프레드 계산
            spread = 0.0
            alert = '---'
            if len(row['Prices']) >= 2:
                min_p = min(row['Prices'])
                max_p = max(row['Prices'])
                spread = ((max_p - min_p) / min_p) * 100
                
                if spread > 0.5:
                    alert = '🚨 HIGH'
                elif spread > 0.05:
                    alert = '🟢 OK'
                else:
                    alert = '✅ LOW'

            row['Spread%'] = f"{spread:.4f}%"
            row['Alert'] = alert
            
            # 가격이 하나라도 있으면 출력 리스트에 추가
            if any(p != '---' for p in [row.get(ex.upper()) for ex in self.all_exchanges]):
                table_data.append(row)
            
        return table_data

    def _print_status(self, table_data: List[Dict]):
        """CMD 화면에 테이블 출력"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\n📊 실시간 데이터 동기화 현황 ({time.strftime('%H:%M:%S')}) - V16 Final")
        print("거래소 명: HL, GRVT, PAC, EXT, LTR")
        print("-" * 110)
        
        # 헤더 출력
        print(f"{'Ticker':<10} | {'HL':<12} | {'GRVT':<12} | {'PAC':<12} | {'EXT':<12} | {'LTR':<12} | {'Spread%':<12} | {'Alert':<5}")
        print("-" * 110)
        
        # 코인별 데이터 출력
        for row in table_data:
            def format_price(p):
                if p == '---': return '---'
                p = float(p)
                if p > 1000: return f"{p:.1f}"
                elif p > 10: return f"{p:.2f}"
                elif p > 1: return f"{p:.3f}"
                else: return f"{p:.5f}"

            line = f"{row['Symbol']:<10} | "
            for key in ['HL', 'GRVT', 'PAC', 'EXT', 'LTR']:
                 line += f"{format_price(row.get(key.upper(), '---')):<12} | "
            
            line += f"{row['Spread%']:<12} | {row['Alert']:<5}"
            
            print(line)

# 실행 블록 (NameError 해결)
if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    monitor = DataFlowMonitor(loop)
    try:
        loop.run_until_complete(monitor.start_monitoring())
    except KeyboardInterrupt:
        loop.run_until_complete(monitor.stop())
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 치명적인 오류 발생: {e}")