# grvt_auth_test.py
# (GRVT 단독 로그인 테스트)

import os
import logging
from dotenv import load_dotenv
from pysdk.grvt_ccxt_ws import GrvtCcxtWS
from pysdk.grvt_ccxt_env import GrvtEnv

# 로깅 설정 (상세 정보 출력)
logging.basicConfig(level=logging.INFO)

# .env 로드
load_dotenv()

def test_grvt_login():
    print("🔍 GRVT 로그인 테스트 시작...")
    
    api_key = os.getenv('GRVT_API_KEY')
    secret_key = os.getenv('GRVT_SECRET_KEY')
    account_id = os.getenv('GRVT_TRADING_ACCOUNT_ID')
    
    if not api_key or not secret_key:
        print("❌ .env 파일에 GRVT 키가 없습니다.")
        return

    try:
        # GRVT 클라이언트 생성 (로그인 시도)
        # 동기 방식 테스트를 위해 loop 없이 생성 시도 (SDK 버전에 따라 다를 수 있음)
        # 안전하게 비동기 래퍼 없이 기본 초기화만 시도
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        params = {
            'api_key': api_key,
            'private_key': secret_key,
            'trading_account_id': account_id
        }
        
        client = GrvtCcxtWS(
            env=GrvtEnv.PROD,
            parameters=params,
            loop=loop
        )
        
        print(f"✅ 객체 생성 성공. 쿠키 상태: {client._cookie}")
        
        if client._cookie:
            print("🎉 로그인 성공! (인증 쿠키 발급됨)")
        else:
            print("❌ 로그인 실패: 쿠키가 발급되지 않았습니다. (서버 문제 또는 IP 차단 가능성)")

    except Exception as e:
        print(f"❌ 테스트 중 에러 발생: {e}")

if __name__ == "__main__":
    test_grvt_auth()