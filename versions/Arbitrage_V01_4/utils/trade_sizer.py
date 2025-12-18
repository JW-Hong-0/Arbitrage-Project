import logging
from decimal import Decimal

logger = logging.getLogger("TradeSizer")

class TradeSizer:
    def __init__(self, hl_exchange, grvt_exchange):
        self.hl = hl_exchange
        self.grvt = grvt_exchange
        self.market_map = {} # { 'BTC': { 'hl': {...}, 'grvt': {...} }, ... }

    async def initialize(self):
        """모든 거래소의 티커 정보를 수집하여 매핑"""
        logger.info("⚙️ [TradeSizer] 시장 데이터 동기화 중...")
        
        # HL 정보 수집
        if self.hl.meta:
            for asset in self.hl.meta['universe']:
                ticker = asset['name']
                stats = self.hl.get_instrument_stats(ticker)
                if ticker not in self.market_map: self.market_map[ticker] = {}
                self.market_map[ticker]['hl'] = stats

        # GRVT 정보 수집 (연결되어 있어야 함)
        if self.grvt.ws and self.grvt.ws.markets:
            for sym, info in self.grvt.ws.markets.items():
                # BTC_USDT_Perp -> BTC 파싱
                base = info.get('base')
                if not base: continue
                
                ticker = base
                stats = self.grvt.get_instrument_stats(ticker)
                
                if ticker not in self.market_map: self.market_map[ticker] = {}
                self.market_map[ticker]['grvt'] = stats
        
        logger.info(f"✅ [TradeSizer] {len(self.market_map)}개 티커 데이터 동기화 완료")

    def calculate_entry_params(self, ticker, price, margin_usd):
        """
        주어진 마진으로 안전하게 진입 가능한 [수량]과 [필요 레버리지] 계산
        """
        if ticker not in self.market_map:
            logger.warning(f"⛔ [TradeSizer] {ticker} 정보 없음")
            return None

        info = self.market_map[ticker]
        hl_stats = info.get('hl', {'min_size': 0, 'max_lev': 0})
        grvt_stats = info.get('grvt', {'min_size': 0, 'max_lev': 0})

        # 1. 최소 주문 수량 확인 (Notional 기준)
        # 양쪽 거래소 중 '더 큰 최소 금액'을 맞춰야 함
        min_qty_hl = hl_stats['min_size']
        min_qty_grvt = grvt_stats['min_size']
        
        # 가격 기준 최소 주문 금액 ($)
        min_notional_hl = min_qty_hl * price
        min_notional_grvt = min_qty_grvt * price
        
        # 교집합: 둘 중 더 빡빡한(큰) 기준을 따름
        required_notional = max(min_notional_hl, min_notional_grvt)

        # 2. 내 마진($15)과 비교하여 레버리지 역산
        # 목표 주문액은 내 마진보다 커야 함. (작으면 내 마진만큼만 사면 됨)
        target_notional = max(required_notional, margin_usd)
        
        required_leverage = target_notional / margin_usd

        # 3. 최대 레버리지 검증
        # 양쪽 거래소 중 '더 낮은' 최대 레버리지를 넘으면 안 됨
        allowed_max_lev = min(hl_stats['max_lev'], grvt_stats['max_lev'])
        
        # 안전장치: 정보가 없어서 0으로 나오면 기본값(10배) 적용
        if allowed_max_lev == 0: allowed_max_lev = 10.0

        if required_leverage > allowed_max_lev:
            logger.warning(f"⛔ [진입불가] {ticker}: 필요 레버리지({required_leverage:.1f}x) > 허용({allowed_max_lev}x)")
            logger.warning(f"   - 최소 필요 주문액: ${required_notional:.2f} (GRVT Min: {min_qty_grvt}, HL Min: {min_qty_hl})")
            return None

        # 4. 결과 반환
        final_qty = target_notional / price
        final_qty *= 1.005 # 0.5% 여유 (가격 변동/반올림 오차 방지)
        
        return {
            'qty': final_qty,
            'leverage': required_leverage,
            'notional': target_notional
        }