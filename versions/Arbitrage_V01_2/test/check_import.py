# check_import.py
import sys
import pprint

print("--- 1. 현재 실행 중인 파이썬 ---")
print(sys.executable)

print("\n--- 2. 파이썬이 패키지를 찾는 폴더 목록 (sys.path) ---")
pprint.pprint(sys.path)

# ⭐️ pip가 설치했다고 말한 그 경로
expected_path = r"c:\users\dasol\appdata\local\programs\python\python313\lib\site-packages"

if expected_path in sys.path:
    print(f"\n✅ 정상: 'sys.path'에 '{expected_path}' 경로가 포함되어 있습니다.")
else:
    print(f"\n❌ [치명적 원인]: 'sys.path'에 '{expected_path}' 경로가 없습니다!")
    print("   -> 1단계를 다시 확인하거나, settings.py 등 다른 파일이 sys.path를 조작하는지 확인하세요.")

print("\n--- 3. 'pysdk' 임포트 시도 ---")
try:
    from pysdk.grvt_ccxt_pro import grvt_ccxt_pro
    print("✅ 'pysdk.grvt_ccxt_pro' 임포트 성공!")
except ImportError as e:
    print(f"❌ 임포트 실패: {e}")