# utils/market_sync.py
import math
import logging

log = logging.getLogger("MarketSync")

class MarketSynchronizer:
    def __init__(self, exchanges: dict):
        self.exchanges = exchanges
        self.common_info = {} # { 'BTC': {'min_qty': 0.001, 'qty_prec': 3, ...}, ... }

    async def warm_up(self):
        """
        [예열] 모든 거래소의 마켓 정보를 수집하고, 교집합 티커에 대해
        가장 보수적인(큰 최소수량, 낮은 정밀도) 기준을 수립합니다.
        """
        log.info("🔥 [초기화] 시장 데이터 동기화 및 예열 시작...")
        
        # 1. 모든 거래소 마켓 로드
        for name, ex in self.exchanges.items():
            await ex.load_markets()
            
        # 2. 공통 기준 수립 (예: BTC)
        # 모든 거래소의 정보를 순회하며 가장 제약이 심한 값을 찾음
        all_tickers = set()
        for ex in self.exchanges.values():
            all_tickers.update(ex.market_info.keys())
            
        for ticker in all_tickers:
            min_qtys = []
            precs = []
            
            for name, ex in self.exchanges.items():
                info = ex.market_info.get(ticker)
                if info:
                    min_qtys.append(info.get('min_size', 0))
                    precs.append(info.get('qty_prec', 0))
            
            if not min_qtys: continue

            # 핵심 로직: 
            # 1. 최소 수량은 가장 큰 값을 기준 (A: 0.001, B: 0.01 -> 0.01이어야 둘 다 통과)
            # 2. 자릿수는 가장 작은 값을 기준 (A: 3자리, B: 2자리 -> 2자리로 맞춰야 함)
            safe_min_qty = max(min_qtys)
            safe_prec = min(precs)
            
            self.common_info[ticker] = {
                'min_qty': safe_min_qty,
                'qty_prec': safe_prec
            }
            
        log.info(f"✅ [동기화] {len(self.common_info)}개 공통 티커 기준 수립 완료")

    def calculate_synced_amount(self, ticker: str, usd_amount: float, price: float) -> float:
        """
        투자금($)을 입력받아 두 거래소 모두에서 통용되는 수량을 계산
        """
        if ticker not in self.common_info:
            return 0.0
            
        info = self.common_info[ticker]
        raw_qty = usd_amount / price
        
        # 공통 정밀도로 내림 처리
        factor = 10 ** info['qty_prec']
        synced_qty = math.floor(raw_qty * factor) / factor
        
        if synced_qty < info['min_qty']:
            return 0.0
            
        return synced_qty