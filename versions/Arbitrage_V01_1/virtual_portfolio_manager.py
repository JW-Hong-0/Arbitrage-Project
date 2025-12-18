# virtual_portfolio_manager.py (수정)
import time
import logging
import settings

log = logging.getLogger("PortfolioManager")

class VirtualPortfolioManager:
    def __init__(self, balances, fees, portfolio_recorder=None):
        self.balances = balances.copy()
        self.fees = fees
        self.recorder = portfolio_recorder
        self.positions = {ex: {} for ex in balances.keys()}
        self.leverage = settings.SIMULATION_CONFIG.get('VIRTUAL_LEVERAGE', 3.0)

    def can_afford(self, exchange, price, qty):
        """[수정됨] 레버리지를 고려하여 증거금만 체크"""
        required_notional = price * qty
        # 증거금 (총 거래금액 / 레버리지) + 수수료
        required_margin = required_notional / self.leverage
        commission = required_notional * self.fees.get(exchange, 0.0005)
        
        total_cost = required_margin + commission
        
        return self.balances.get(exchange, 0) >= total_cost

    def add_trade(self, exchange, symbol, side, price, qty, trade_type, pnl=0):
        # ... (생략: 필요한 경우 전체 코드를 제공하겠습니다) ...

        value = price * qty
        fee_rate = self.fees.get(exchange, 0.0)
        commission = value * fee_rate

        # 1. 잔고 차감/가산 (증거금 모델 반영)
        required_margin = value / self.leverage
        
        if trade_type == 'ENTRY':
            # 매수/매도 진입 시: 증거금과 수수료만 차감
            self.balances[exchange] -= (required_margin + commission)
        
        elif trade_type == 'EXIT':
            # 청산 시: 증거금 반환 + PnL 정산 - 수수료 차감
            # (PnL은 monitor에서 계산해서 넘어옴)
            self.balances[exchange] += (required_margin + pnl - commission)

        # 2. 포지션 업데이트 (Active PnL을 위해 현재 가격 정보도 저장)
        if trade_type == 'ENTRY':
            self.positions[exchange][symbol] = {
                'side': side,
                'price': price,
                'qty': qty,
                'entry_time': time.time(),
                'pnl': 0.0 # 초기 미실현 PnL
            }
        elif trade_type == 'EXIT':
            if symbol in self.positions[exchange]:
                del self.positions[exchange][symbol]
        
        # 3. 기록 (trade_type 오류 해결)
        if self.recorder:
            self.recorder.log_trade({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'exchange': exchange,
                'symbol': symbol,
                'type': trade_type, # [수정] trade_type 키는 그대로 사용
                'side': side,
                'price': price,
                'qty': qty,
                'fee': commission,
                'pnl': pnl,
                'balance_after': self.balances[exchange]
            })