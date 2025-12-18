import asyncio
import sys
import os
import time
from typing import Dict, List, Any
from collections import defaultdict
import logging

# Python 3.9+에서 List[Dict] 같은 타입 힌트를 쓰기 위해 필요
from typing import List, Dict

# 로깅 설정 (CMD 화면에만 깔끔하게 출력)
logging.basicConfig(level=loggingINFO, format='%(message)s')
logger = logging.getLogger("CrossCheckMonitor")
logger.setLevel(logging.INFO)

# --- ArbitrageBot의 핵심 구조를 상속받아 데이터만 읽어옵니다. ---
try:
    # 이 부분은 ArbitrageBot.py의 클래스 정의를 복사해야 합니다.
    # 하지만 파일이 많으므로, 필요한 모듈만 임포트하고 구조를 재현합니다.
    from arbitrage_bot import ArbitrageBot
    import settings
    from exchange_apis import Exchange
except ImportError as e:
    print(f"❌ 필수 모듈 로드 실패 (settings, arbitrage_bot 등): {e}")
    sys.exit(1)

# =========================================================================
# 💡 핵심: ArbitrageBot을 상속받아 PnL/Trade 로직을 끄고 데이터만 검증합니다.
# =========================================================================

class DataFlowMonitor(ArbitrageBot):
    def __init__(self, loop):
        super().__init__(loop)
        self.all_exchanges = list(self.exchanges.keys())
        # Active Position 로직은 필요 없으므로 끄기
        self.is_running = True 
        
    async def start_monitoring(self):
        log.info("📊 5대 거래소 실시간 데이터 크로스 체크 시작")
        
        # 1. 웹소켓 연결 (Data Ingestion 시작)
        await self._connect_and_subscribe()
        
        # 2. 실시간 출력 루프 시작
        await self._realtime_output_loop()

    # 오버라이드: 이 테스터에서는 계산을 하지 않고, 데이터 수신만 합니다.
    async def _on_market_update(self, bbo_data: Dict):
        pass 
        
    # 오버라이드: 봇의 _market_scanner_loop 대신 간단한 출력 루프 사용
    async def _realtime_output_loop(self):
        while True:
            # 1. 데이터 수집 및 계산
            table_data = self._get_current_prices()
            
            # 2. 출력
            self._print_status(table_data)
            
            await asyncio.sleep(0.5)

    def _get_current_prices(self) -> List[Dict]:
        """현재 BBO 캐시 상태를 종합하여 테이블 데이터로 반환"""
        table_data = []
        current_time = time.time()
        
        # 1시간 유효 기간 (3600초)
        VALID_WINDOW = 3600.0 
        
        # settings.py에 정의된 모든 타겟 코인 순회
        for ticker in settings.TARGET_PAIRS_CONFIG.keys():
            row = {'Symbol': ticker, 'Alert': ' ', 'Prices': []}
            
            # 2. 5개 거래소 캐시 조회
            for ex_name in self.all_exchanges:
                exchange: Exchange = self.exchanges[ex_name]
                bbo = exchange.get_bbo(ticker)
                
                price_bid = bbo.get('bid', 0.0) if bbo else 0.0
                data_time = bbo.get('timestamp', 0)
                
                # 3. 유효성 체크
                if price_bid > 0 and (current_time - data_time < VALID_WINDOW):
                    row[ex_name.upper()] = price_bid # BID 가격을 사용
                    row['Prices'].append(price_bid)
                else:
                    row[ex_name.upper()] = '---'

            # 4. 스프레드 및 알림 계산
            if len(row['Prices']) >= 2:
                min_p = min(row['Prices'])
                max_p = max(row['Prices'])
                spread_pct = ((max_p - min_p) / min_p) * 100
                row['Spread%'] = f"{spread_pct:.4f}%"
                
                if spread_pct > 0.5:
                    row['Alert'] = '🚨' # 0.5% 이상이면 경고
                elif spread_pct < 0.01:
                    row['Alert'] = '✅' # 0.01% 미만은 안정
                else:
                    row['Alert'] = '🟢'

            # 5. 최종 데이터 정리 (출력용)
            if any(p != '---' for p in [row.get(ex.upper()) for ex in self.all_exchanges]):
                # 유효한 가격이 하나라도 있을 때만 출력 리스트에 추가
                final_row = {
                    'Symbol': row['Symbol'],
                    'HL': row.get('HL', '---'),
                    'GRVT': row.get('GRVT', '---'),
                    'PAC': row.get('PAC', '---'),
                    'EXT': row.get('EXT', '---'),
                    'LTR': row.get('LTR', '---'),
                    'Spread%': row.get('Spread%', '---'),
                    'Alert': row['Alert']
                }
                table_data.append(final_row)
            
        return table_data

    def _print_status(self, table_data: List[Dict]):
        """CMD 화면에 테이블 출력"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\n📊 실시간 데이터 크로스 체크 ({time.strftime('%H:%M:%S')}) - V16 Final")
        print("-" * 110)
        
        # 헤더 출력
        print(f"{'Symbol':<10} | {'HL':<12} | {'GRVT':<12} | {'PAC':<12} | {'EXT':<12} | {'LTR':<12} | {'Spread%':<12} | {'Alert':<5}")
        print("-" * 110)
        
        # 코인별 데이터 출력
        for row in table_data:
            # 가격 포맷팅 (출력용)
            def format_price(p):
                if p == '---': return '---'
                p = float(p)
                if p > 1000: return f"{p:.1f}"
                elif p > 10: return f"{p:.2f}"
                elif p > 1: return f"{p:.3f}"
                else: return f"{p:.5f}"

            line = f"{row['Symbol']:<10} | "
            for key in ['HL', 'GRVT', 'PAC', 'EXT', 'LTR']:
                 line += f"{format_price(row.get(key, '---')):<12} | "
            
            line += f"{row['Spread%']:<12} | {row['Alert']:<5}"
            
            print(line)