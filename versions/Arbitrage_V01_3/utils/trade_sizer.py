import logging
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger("TradeSizer")

class TradeSizer:
    def __init__(self, hl_exchange, grvt_exchange):
        self.hl = hl_exchange
        self.grvt = grvt_exchange
        self.market_map = {}

    async def initialize(self):
        logger.info("⚙️ [TradeSizer] 시장 데이터 동기화 중...")
        # 1. HL 정보 수집
        if hasattr(self.hl, 'meta') and self.hl.meta:
            for asset in self.hl.meta['universe']:
                ticker = asset['name']
                self.market_map[ticker] = {'hl': self.hl.get_instrument_stats(ticker)}

        # 2. GRVT 정보 수집 (market_info 직접 참조)
        for ticker, info in self.grvt.market_info.items():
            if ticker not in self.market_map: self.market_map[ticker] = {}
            self.market_map[ticker]['grvt'] = self.grvt.get_instrument_stats(ticker)
        
        logger.info(f"✅ [TradeSizer] {len(self.market_map)}개 티커 데이터 동기화 완료")

    def calculate_entry_params(self, ticker, price, target_size_usd):
        """
        목표 금액($)을 기준으로 거래소 정밀도에 맞춘 정확한 수량을 계산합니다.
        """
        if ticker not in self.market_map:
            return None

        info = self.market_map[ticker]
        hl_stats = info.get('hl', {'min_size': 0.001, 'max_lev': 50.0})
        grvt_stats = info.get('grvt', {'min_size': 0.01, 'max_lev': 20.0}) # ETH 기준 0.01 적용

        # 1. 양쪽 거래소가 모두 수용 가능한 최소 주문 단위(Step Size) 선택
        min_step = max(hl_stats['min_size'], grvt_stats['min_size'])

        # 2. 수량 계산 및 정밀도 보정 (가장 중요)
        # Decimal을 사용하여 부동소수점 오차를 방지하고 min_step 배수로 내림 처리
        raw_qty = target_size_usd / price
        final_qty = float((Decimal(str(raw_qty)) // Decimal(str(min_step))) * Decimal(str(min_step)))

        if final_qty <= 0:
            return None

        return {
            'qty': final_qty,
            'notional': final_qty * price
        }