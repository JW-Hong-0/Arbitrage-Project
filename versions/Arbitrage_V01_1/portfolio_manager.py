import pandas as pd
import time
import os
import logging
from typing import Dict, Any, List

# 로깅 설정
log = logging.getLogger("PortfolioManager")
log.setLevel(logging.INFO)

class PortfolioManager:
    """
    거래 기록을 관리하고 엑셀 파일로 내보내는 클래스
    """
    def __init__(self):
        # 전체 거래 기록 리스트
        self.trade_log: List[Dict[str, Any]] = []
        
        # 파일 경로
        self.file_path = 'virtual_arbitrage_log.xlsx'
        
        # 엑셀 저장에 필요한 컬럼 정의 (DF 생성 시 컬럼 이름 고정)
        self.columns = [
            'timestamp', 'exchange', 'symbol', 'type', 'side', 
            'price', 'qty', 'fee', 'pnl', 'balance_after'
        ]

    def log_trade(self, log_entry: Dict[str, Any]):
        """
        거래 기록을 리스트에 추가하고, 누락된 키를 None으로 채움 (DF 생성 안정화)
        """
        # 필수 키가 없으면 에러 방지
        validated_entry = {col: log_entry.get(col) for col in self.columns}
        self.trade_log.append(validated_entry)

    def export_trade_log_to_excel(self, grvt_balance=None, based_balance=None):
        """
        거래 기록을 Pandas DataFrame으로 변환하여 엑셀 파일로 저장
        
        **주의: 봇의 _periodic_save_loop에서 인자 없이 호출됩니다.**
        """
        if not self.trade_log:
            return

        try:
            # [수정] self.trade_log를 기반으로 DataFrame 생성. columns를 명시하여 키 누락 에러 방지
            df = pd.DataFrame(self.trade_log, columns=self.columns)
            
            # 파일 저장
            df.to_excel(self.file_path, index=False)
            
            log.info(f"💾 거래 기록 저장 완료: {self.file_path}")

        except Exception as e:
            # [수정] 엑셀 저장 오류가 나면 CSV로라도 백업 시도
            backup_path = self.file_path.replace('.xlsx', '_backup.csv')
            try:
                pd.DataFrame(self.trade_log).to_csv(backup_path, index=False)
                log.error(f"❌ 엑셀 저장 실패: {e}. CSV로 백업 완료: {backup_path}")
            except:
                 log.error(f"❌ 엑셀 및 CSV 저장 모두 실패.")