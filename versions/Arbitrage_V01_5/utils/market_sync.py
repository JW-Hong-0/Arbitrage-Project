# utils/market_sync.py
import math
import logging
import settings

log = logging.getLogger("MarketSync")

class MarketSynchronizer:
    def __init__(self, exchanges: dict):
        self.exchanges = exchanges
        # common_info: { 'BTC': {'min_qty': 0.001, 'qty_prec': 3, 'max_lev': 50}, ... }
        self.common_info = {} 

    async def warm_up(self):
        """
        [예열] 모든 거래소의 마켓 정보를 수집하고, 교집합 티커에 대해
        가장 보수적인(큰 최소수량, 낮은 정밀도, 낮은 레버리지) 기준을 수립합니다.
        """
        log.info("🔥 [초기화] 시장 데이터 동기화 및 예열 시작...")
        
        # 1. 모든 거래소 마켓 로드
        for name, ex in self.exchanges.items():
            await ex.load_markets()
            
        # 2. 검사할 전체 티커 목록 생성
        all_tickers = set(settings.TARGET_PAIRS_CONFIG.keys())
        for ex in self.exchanges.values():
            all_tickers.update(ex.market_info.keys())
            
        sync_count = 0
        
        for ticker in all_tickers:
            min_qtys = []
            precs = []
            max_levs = []
            
            # 2개 이상 거래소에서 지원하는지 확인
            supported_exchanges = 0
            for name, ex in self.exchanges.items():
                info = ex.market_info.get(ticker)
                if info:
                    min_qtys.append(info.get('min_size', 0))
                    precs.append(info.get('qty_prec', 0))
                    max_levs.append(info.get('max_lev', 1))
                    supported_exchanges += 1
            
            if supported_exchanges < 2:
                continue

            # [보수적인 기준 적용]
            safe_min_qty = max(min_qtys)
            safe_prec = min(precs)
            safe_max_lev = min(max_levs) # 가장 낮은 거래소의 최대 레버리지를 기준
            
            self.common_info[ticker] = {
                'min_qty': safe_min_qty,
                'qty_prec': safe_prec,
                'max_lev': safe_max_lev
            }
            sync_count += 1
            
        log.info(f"✅ [동기화] {sync_count}개 공통 티커 기준 수립 완료")

    def calculate_smart_order_params(self, ticker: str, price: float):
        """
        [핵심 알고리즘] 사용자 설정과 거래소 제약을 고려하여
        최적의 레버리지와 주문 수량을 계산합니다.
        
        Returns:
            (leverage, quantity, position_size_usd)
        """
        if ticker not in self.common_info or price <= 0:
            return 1, 0.0, 0.0
            
        sync_info = self.common_info[ticker]
        
        # 1. 사용자 설정 가져오기 (settings.py)
        # 예: TRADE_SIZE_USD(목표 포지션) = 200, MAX_MARGIN_USD = 15, TARGET_LEV = 15
        user_config = settings.TARGET_PAIRS_CONFIG.get(ticker, {})
        
        # 설정이 없으면 기본값 사용
        target_pos_usd = user_config.get('trade_size_fixed_usd', 45.0) 
        target_lev = user_config.get('target_leverage', 15)
        max_margin = user_config.get('max_margin_usd', 15.0)
        
        # 2. 유효 레버리지 계산 (Min of Target vs Exchange Max)
        exchange_max_lev = sync_info['max_lev']
        effective_lev = min(target_lev, exchange_max_lev)
        
        # 3. 포지션 규모 산출 (Dual Constraint)
        # 조건 A: 마진으로 가능한 최대 포지션 = 마진 * 레버리지
        limit_by_margin = max_margin * effective_lev
        
        # 조건 B: 사용자가 원했던 목표 포지션
        # 최종 포지션 = 둘 중 작은 값
        final_pos_usd = min(target_pos_usd, limit_by_margin)
        
        # 4. 수량 계산 (정밀도 반영)
        raw_qty = final_pos_usd / price
        
        prec = sync_info['qty_prec']
        min_qty = sync_info['min_qty']
        
        if raw_qty < min_qty:
            return effective_lev, 0.0, 0.0

        # 정밀도 처리 (Floor)
        if prec <= 0:
             step = 10 ** abs(prec)
             final_qty = math.floor(raw_qty / step) * step
        else:
            factor = 10 ** prec
            final_qty = math.floor(raw_qty * factor) / factor
            
        return effective_lev, final_qty, final_pos_usd