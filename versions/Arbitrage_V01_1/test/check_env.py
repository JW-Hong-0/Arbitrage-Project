# check_env.py
# (모든 문제의 근본 원인을 찾기 위한 최종 진단 스크립트)

import sys
import os
import pprint
import traceback

print("--- 1. 현재 실행 중인 파이썬 ---")
print(sys.executable)

print("\n--- 2. [가장 중요] 'PYTHONPATH' 환경 변수 확인 ---")
# ⭐️ 이 변수가 설정되어 있다면, 100% 이 문제입니다.
python_path_env = os.getenv('PYTHONPATH')
if python_path_env:
    print(f"❌ [치명적 원인 발견]: 'PYTHONPATH' 변수가 설정되어 있습니다!")
    print(f"   -> {python_path_env}")
    print("   -> 이 변수는 파이썬 재설치로 제거되지 않습니다.")
    print("   -> '고급 시스템 설정 > 환경 변수'에서 이 변수를 '삭제'해야 합니다.")
else:
    print("✅ 'PYTHONPATH' 변수가 설정되어 있지 않습니다. (정상)")


print("\n--- 3. [가장 중요] 파이썬이 실제로 패키지를 찾는 경로 (sys.path) ---")
# ⭐️ 파이썬이 '어디를' 뒤지고 있는지 실제 목록을 봅니다.
pprint.pprint(sys.path)


print("\n--- 4. 'Lib\\site-packages' 경로가 포함되어 있는지 확인 ---")
# ⭐️ 우리가 설치한 경로
expected_path_fragment = os.path.join("Python313", "Lib", "site-packages")
found = False
for path in sys.path:
    if expected_path_fragment in path:
        found = True
        break

if found:
    print(f"✅ '...{expected_path_fragment}' 경로가 sys.path에 포함되어 있습니다.")
else:
    print(f"❌ [치명적 원인 발견]: '...{expected_path_fragment}' 경로가 sys.path에 없습니다!")
    print(f"   -> 'PYTHONPATH'가 sys.path를 오염시켰을 확률이 99%입니다.")

print("\n--- 5. 'grvt-pysdk' 임포트 시도 ---")
try:
    from pysdk.grvt_ccxt import grvt_ccxt
    print("✅ [성공] 'from pysdk.grvt_ccxt import grvt_ccxt' 임포트 성공!")
except ImportError:
    print("❌ [실패] 'ImportError' 발생.")
    traceback.print_exc()
except Exception as e:
    print(f"❌ [실패] '{type(e).__name__}' 발생.")
    traceback.print_exc()