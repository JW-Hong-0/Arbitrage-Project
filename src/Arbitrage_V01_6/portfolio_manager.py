# portfolio_manager.py
import pandas as pd
import logging
import time
import os
from datetime import datetime

log = logging.getLogger("PortfolioManager")

class PortfolioManager:
    def __init__(self, exchanges: dict, filename="arbitrage_log_v5.xlsx"):
        self.exchanges = exchanges
        self.filename = filename
        self.trade_history = []
        self.balance_history = []
        
        # 엑셀 파일 초기화
        self._initialize_excel()

    def _initialize_excel(self):
        """엑셀 파일이 없으면 헤더 생성"""
        if not os.path.exists(self.filename):
            try:
                with pd.ExcelWriter(self.filename, mode='w', engine='openpyxl') as writer:
                    pd.DataFrame(columns=['Time', 'Total_Equity', 'HL', 'GRVT', 'PAC', 'LTR', 'EXT']).to_excel(writer, sheet_name='Balance', index=False)
                    pd.DataFrame(columns=['Time', 'Symbol', 'Type', 'Side', 'Qty', 'Price', 'Exchange', 'PnL']).to_excel(writer, sheet_name='Trades', index=False)
                log.info(f"📁 엑셀 파일 생성 완료: {self.filename}")
            except Exception as e:
                log.error(f"❌ 엑셀 초기화 실패: {e}")

    async def update_balances(self):
        """모든 거래소 잔고 조회 및 스냅샷 저장"""
        snapshot = {
            'Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Total_Equity': 0.0
        }
        
        log.info("💰 잔고 스냅샷 촬영 중...")
        for name, ex in self.exchanges.items():
            try:
                bal = await ex.get_balance()
                equity = bal['equity'] if bal else 0.0
                snapshot[name] = equity
                snapshot['Total_Equity'] += equity
                
                # 포지션 정보도 로깅 (선택 사항)
                if bal and bal['positions']:
                    pos_str = ", ".join([f"{p['symbol']}:{p['size']}" for p in bal['positions']])
                    log.info(f"   └ {name}: ${equity:.2f} ({pos_str})")
                else:
                    log.info(f"   └ {name}: ${equity:.2f}")
                    
            except Exception as e:
                log.error(f"⚠️ {name} 잔고 조회 에러: {e}")
                snapshot[name] = 0.0

        self.balance_history.append(snapshot)
        self._save_to_excel('Balance', pd.DataFrame([snapshot]))
        log.info(f"💵 총 자산: ${snapshot['Total_Equity']:.2f}")

    def log_trade(self, trade_data: dict):
        """
        매매 발생 시 기록
        trade_data = {
            'Symbol': 'ETH', 'Type': 'Entry', 'Side': 'Buy/Sell', 
            'Qty': 0.1, 'Price': 3200, 'Exchange': 'HL-GRVT', 'PnL': 0
        }
        """
        record = {
            'Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **trade_data
        }
        self.trade_history.append(record)
        self._save_to_excel('Trades', pd.DataFrame([record]))
        log.info(f"📝 매매 기록 저장: {record['Type']} {record['Symbol']}")

    def _save_to_excel(self, sheet_name, df_new):
        """데이터를 엑셀에 추가 (Append)"""
        try:
            # 기존 파일이 있으면 읽어서 합침 (단순 Append 모드가 제한적이므로)
            if os.path.exists(self.filename):
                with pd.ExcelWriter(self.filename, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                    # 해당 시트의 마지막 행 찾기 로직이 복잡하므로, 
                    # 실전에서는 CSV로 저장 후 나중에 합치거나, 
                    # 여기서는 메모리에 있는 전체 히스토리를 덮어쓰는 방식을 권장합니다.
                    # 하지만 성능을 위해 여기서는 간단히 '새 데이터'만 추가하는 로직 대신
                    # 전체 데이터를 다시 쓰는 방식을 사용하겠습니다 (안전성 우선).
                    pass

            # 안전한 저장 방식: 전체 데이터 덮어쓰기 (데이터가 아주 많지 않으므로 가능)
            all_balance = pd.DataFrame(self.balance_history)
            all_trades = pd.DataFrame(self.trade_history)
            
            with pd.ExcelWriter(self.filename, mode='w', engine='openpyxl') as writer:
                if not all_balance.empty:
                    all_balance.to_excel(writer, sheet_name='Balance', index=False)
                if not all_trades.empty:
                    all_trades.to_excel(writer, sheet_name='Trades', index=False)
                    
        except Exception as e:
            log.error(f"❌ 엑셀 저장 실패: {e}")