import time
import logging
import settings
from typing import Dict, Any

log = logging.getLogger("PortfolioManager")

class VirtualPortfolioManager:
    def __init__(self, balances, fees, portfolio_recorder=None):
        self.balances = balances.copy()
        self.locked_margins = {ex: 0.0 for ex in balances}
        self.fees = fees
        self.recorder = portfolio_recorder
        self.positions = {ex: {} for ex in balances.keys()}
        self.leverage = settings.SIMULATION_CONFIG.get('VIRTUAL_LEVERAGE', 3.0)

    def can_afford(self, exchange, price, qty):
        """
        진입 가능 여부 확인
        필요 금액 = (주문가치 / 레버리지) + 예상 수수료
        """
        notional_value = price * qty
        required_margin = notional_value / self.leverage
        estimated_fee = notional_value * self.fees.get(exchange, 0.0005)
        
        total_cost = required_margin + estimated_fee
        
        # 현재 잔고가 필요 비용보다 많은지 확인
        return self.balances.get(exchange, 0) >= total_cost

    def add_trade(self, exchange, symbol, side, price, qty, trade_type, pnl=0):
        # [신규] 가상 슬리피지 적용 (현실성 반영)
        # 매수(BUY)는 더 비싸게, 매도(SELL)는 더 싸게 체결된다고 가정
        # 1. 주문 총 가치 (Notional Value)
        notional_value = price * qty
        
        # 2. 수수료 계산 (총 가치 * 수수료율)
        # 예: $50 * 0.00045 = $0.0225 (정상)
        fee_rate = self.fees.get(exchange, 0.0)
        commission = notional_value * fee_rate

        # 3. 필요 증거금 (총 가치 / 레버리지)
        # 예: $50 / 3 = $16.66 (내 돈은 이만큼만 잠김)
        required_margin = notional_value / self.leverage
        
        if trade_type == 'ENTRY':
            # 진입: (증거금 + 수수료) 차감
            self.balances[exchange] -= (required_margin + commission)
            self.locked_margins[exchange] += required_margin
            
            self.positions[exchange][symbol] = {
                'side': side, 'price': price, 'qty': qty, 
                'entry_time': time.time(), 'margin': required_margin
            }
            
        elif trade_type == 'EXIT':
            if symbol in self.positions[exchange]:
                # 청산: 잠겼던 증거금 돌려받음 + PnL 반영 - 수수료 차감
                original_margin = self.positions[exchange][symbol]['margin']
                self.locked_margins[exchange] -= original_margin
                
                self.balances[exchange] += (original_margin + pnl - commission)
                del self.positions[exchange][symbol]
        
        # 로그 기록
        if self.recorder:
            total_equity = self.balances[exchange] + self.locked_margins[exchange]
            self.recorder.log_trade({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'exchange': exchange,
                'symbol': symbol,
                'type': trade_type,
                'side': side,
                'price': price,
                'qty': qty,
                'fee': commission, # 이제 정상적인 수수료가 기록됨
                'pnl': pnl if trade_type == 'EXIT' else 0,
                'balance_after': total_equity
            })

    def get_active_position(self, ticker):
        long_pos = None; short_pos = None
        for ex, positions in self.positions.items():
            if ticker in positions:
                pos = positions[ticker]
                if pos['side'] == 'BUY': long_pos = {'ex': ex, 'data': pos}
                elif pos['side'] == 'SELL': short_pos = {'ex': ex, 'data': pos}
        if long_pos and short_pos:
            return {'long': long_pos, 'short': short_pos}
        return None

    def get_total_equity(self, exchange):
        return self.balances.get(exchange, 0) + self.locked_margins.get(exchange, 0)