import pandas as pd
import logging
from typing import Dict, Any, List
from datetime import datetime

log = logging.getLogger("PortfolioManager")
log.setLevel(logging.INFO)

class PortfolioManager:
    def __init__(self):
        self.trade_log: List[Dict[str, Any]] = []
        self.file_path = 'virtual_arbitrage_log.xlsx'
        self.columns = [
            'timestamp', 'exchange', 'symbol', 'type', 'side', 
            'price', 'qty', 'fee', 'pnl', 'balance_after'
        ]

    def log_trade(self, log_entry: Dict[str, Any]):
        validated_entry = {col: log_entry.get(col) for col in self.columns}
        if validated_entry.get('pnl') is None: validated_entry['pnl'] = 0.0
        self.trade_log.append(validated_entry)

    def export_trade_log_to_excel(self, balances: Dict[str, float] = None):
        if not self.trade_log:
            log.info("저장할 거래 기록이 없습니다.")
            return

        try:
            # 1. 메인 로그
            df_log = pd.DataFrame(self.trade_log, columns=self.columns)
            for col in ['price', 'qty', 'fee', 'pnl']:
                df_log[col] = pd.to_numeric(df_log[col], errors='coerce').fillna(0)
            
            # 거래량(USD Volume) 계산
            df_log['volume'] = df_log['price'] * df_log['qty']

            # 2. 거래소별 통계 (Exchange Analysis)
            ex_stats = []
            if balances:
                all_exchanges = set(df_log['exchange'].unique()) | set(balances.keys())
                for ex in all_exchanges:
                    ex_df = df_log[df_log['exchange'] == ex]
                    # 진입 횟수만 카운트 (청산 제외)
                    entry_count = len(ex_df[ex_df['type'] == 'ENTRY'])
                    
                    ex_stats.append({
                        'Exchange': ex,
                        'Current Equity': balances.get(ex, 0.0),
                        'Net PnL': ex_df['pnl'].sum(),
                        'Total Fees': ex_df['fee'].sum(),
                        'Entry Count': entry_count,
                        'Total Volume': ex_df['volume'].sum()
                    })
            df_ex = pd.DataFrame(ex_stats)

            # 3. 전체 요약 (Summary)
            summary_data = [{
                'Metric': 'Total Net PnL', 'Value': df_log['pnl'].sum()
            }, {
                'Metric': 'Total Fees Paid', 'Value': df_log['fee'].sum()
            }, {
                'Metric': 'Total Volume', 'Value': df_log['volume'].sum()
            }, {
                'Metric': 'Total Entries', 'Value': df_ex['Entry Count'].sum() if not df_ex.empty else 0
            }, {
                'Metric': 'Report Time', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }]
            df_sum = pd.DataFrame(summary_data)

            with pd.ExcelWriter(self.file_path, engine='openpyxl') as writer:
                df_sum.to_excel(writer, sheet_name='Summary', index=False)
                df_ex.to_excel(writer, sheet_name='Exchange Analysis', index=False)
                df_log.to_excel(writer, sheet_name='Trade Log', index=False)
                
            log.info(f"💾 엑셀 리포트 저장 완료: {self.file_path}")

        except Exception as e:
            log.error(f"엑셀 저장 실패: {e}")