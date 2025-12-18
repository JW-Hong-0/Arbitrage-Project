# check_import_v2.py
# (오류의 전체 Traceback을 확인하기 위한 최종 진단 스크립트)

import sys
import traceback
import os

print("--- 1. 현재 실행 중인 파이썬 ---")
print(sys.executable)
print(f"(PID: {os.getpid()})") # (프로세스 ID)

print("\n--- 2. 'pysdk.grvt_ccxt_pro' 모듈을 직접 임포트하여 상세 오류 추적 ---")
print("="*60)
# ⭐️ try...except 블록에서 Traceback을 직접 출력하여
# 숨겨진 '진짜 원인'을 확인합니다.

try:
    from pysdk.grvt_ccxt_pro import grvt_ccxt_pro
    
    print("\n✅✅✅ [성공] 임포트 성공! ✅✅✅")
    print("이 메시지가 보인다면, 문제는 VS Code 캐시였거나 해결되었습니다.")

except ImportError as e:
    print("\n--- ❌ [ImportError] 임포트 실패 ---")
    print("이것이 진짜 오류(Root Cause)일 가능성이 높습니다.")
    # ⭐️ 전체 오류 스택을 출력
    traceback.print_exc()

except Exception as e:
    print(f"\n--- ❌ [{type(e).__name__}] 예상치 못한 오류 ---")
    # ImportError가 아닌 다른 오류 (예: SyntaxError)
    traceback.print_exc()

print("="*60)
print("\n--- 3. 진단 완료 ---")