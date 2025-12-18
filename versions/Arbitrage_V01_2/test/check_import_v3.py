# check_import_v3.py
# (grvt-pysdk 내부의 '숨겨진' 임포트 오류를 잡기 위한 최종 진단 스크립트)

import sys
import os
import traceback
import importlib # ⭐️ 모듈을 수동으로 로드하기 위한 라이브러리

print(f"--- 1. 현재 실행 중인 파이썬 ---\n{sys.executable}")

print(f"\n--- 2. 'pysdk' 패키지 경로 확인 ---")
try:
    import pysdk
    print(f"✅ 'pysdk' 패키지 위치: {pysdk.__path__}")
except Exception as e:
    print(f"❌ 'pysdk' 자체를 임포트할 수 없습니다: {e}")
    sys.exit(1)


print("\n--- 3. 'pysdk.grvt_ccxt' 모듈 로드 시도 (진짜 오류 추적) ---")
print("="*60)
try:
    # ⭐️ 'from'을 쓰지 않고, 모듈 자체를 수동으로 로드하여
    # ⭐️ '내부 오류' (예: 순환 참조, 누락된 하위 종속성)를 잡습니다.
    
    importlib.import_module("pysdk.grvt_ccxt")
    
    print("✅ [1단계 성공] 'pysdk.grvt_ccxt' 모듈 로드 성공.")
    
except Exception as e:
    print(f"\n❌ [치명적 오류 발견] 'pysdk.grvt_ccxt' 모듈을 로드하는 중 실패했습니다.")
    print(f"   이것이 모든 문제의 '진짜 원인(Root Cause)'입니다.")
    print("="*60)
    traceback.print_exc() # ⭐️⭐️⭐️
    print("="*60)
    sys.exit(1)


print("\n--- 4. 'grvt_ccxt' 클래스 임포트 시도 ---")
try:
    from pysdk.grvt_ccxt import grvt_ccxt
    print("✅✅✅ [완벽 성공] 'grvt_ccxt' 클래스 임포트 성공!")
    print(grvt_ccxt) # 클래스 정보 출력
    
except ImportError as ie:
    print(f"\n❌ [2단계 실패] 모듈 로드는 성공했으나, 클래스 임포트에 실패했습니다.")
    print(f"   (이론적으로 발생하면 안 되는 오류입니다)")
    print("="*60)
    traceback.print_exc()
    print("="*60)

print("\n--- 5. 진단 완료 ---")