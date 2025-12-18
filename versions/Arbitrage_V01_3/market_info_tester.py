import requests
import json
import logging
import sys
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("MarketInfoTester")

class MarketInfoTester:
    def __init__(self):
        self.results = {}

    def test_hyperliquid(self):
        log.info("--- [1] Hyperliquid Market Info ---")
        url = "https://api.hyperliquid.xyz/info"
        headers = {"Content-Type": "application/json"}
        body = {"type": "meta"}
        
        try:
            res = requests.post(url, json=body, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                universe = data.get('universe', [])
                log.info(f"✅ 수신 성공! 총 {len(universe)}개 심볼 발견")
                
                eth_info = next((item for item in universe if item['name'] == 'ETH'), None)
                if eth_info:
                    log.info(f"   👉 ETH 예시: 소수점 {eth_info.get('szDecimals')}자리, 최대 레버리지 {eth_info.get('maxLeverage')}x")
                    self.results['hyperliquid'] = True
                else:
                    log.warning("   ⚠️ ETH 심볼을 찾을 수 없음")
            else:
                log.error(f"❌ 요청 실패 (Status: {res.status_code})")
        except Exception as e:
            log.error(f"❌ 에러 발생: {e}")

    def test_pacifica(self):
        log.info("\n--- [2] Pacifica Market Info (검증 필요) ---")
        # 알려진 정보가 없어 추정 URL 사용 (실패 가능성 높음 -> 수동 설정 권장)
        endpoints = [
            "https://api.pacifica.fi/api/v1/info",
            "https://api.pacifica.fi/api/v1/meta",
            "https://api.pacifica.fi/api/v1/markets"
        ]
        
        success = False
        for url in endpoints:
            try:
                res = requests.get(url, timeout=3)
                if res.status_code == 200:
                    log.info(f"✅ {url} 수신 성공!")
                    log.info(f"📄 데이터 일부: {res.text[:100]}...")
                    success = True
                    self.results['pacifica'] = True
                    break
            except:
                pass
        
        if not success:
            log.warning("⚠️ 파시피카는 Public Info API를 찾지 못했습니다. (수동 설정 필요)")

    def test_lighter(self):
        log.info("\n--- [3] Lighter Market Info (업데이트됨) ---")
        # 사용자 제공 URL 적용
        url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
        
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                order_books = data.get('order_books', [])
                log.info(f"✅ 수신 성공! 총 {len(order_books)}개 심볼 발견")
                
                # 샘플 출력 (ETH)
                eth_info = next((item for item in order_books if item['symbol'] == 'ETH'), None)
                if eth_info:
                    # JSON 필드 매핑 확인
                    min_size = eth_info.get('min_base_amount')
                    qty_prec = eth_info.get('supported_size_decimals')
                    price_prec = eth_info.get('supported_price_decimals')
                    
                    log.info(f"   👉 ETH 예시:")
                    log.info(f"      - 최소 주문 수량: {min_size}")
                    log.info(f"      - 수량 자릿수(Decimals): {qty_prec}")
                    log.info(f"      - 가격 자릿수(Decimals): {price_prec}")
                    self.results['lighter'] = True
                else:
                    log.warning("   ⚠️ ETH 심볼을 찾을 수 없음")
            else:
                log.error(f"❌ 요청 실패 (Status: {res.status_code})")
        except Exception as e:
            log.error(f"❌ 에러 발생: {e}")

    def test_extended(self):
        log.info("\n--- [4] Extended Market Info (검증 필요) ---")
        # Extended URL 추정
        url = "https://api.extended.exchange/v1/info" 
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                log.info(f"✅ 수신 성공!")
                log.info(f"📄 내용: {res.text[:100]}...")
                self.results['extended'] = True
            else:
                log.info(f"❌ 요청 실패 (Status: {res.status_code})")
        except Exception as e:
            log.info(f"❌ 에러 발생: {e}")

    def run(self):
        print("==========================================")
        print("🌍 거래소 마켓 정보(자릿수/레버리지) 수집 테스트")
        print("==========================================")
        
        self.test_hyperliquid()
        self.test_pacifica()
        self.test_lighter()
        self.test_extended()
        
        print("\n==========================================")
        print("📊 [최종 결과 요약]")
        for ex, success in self.results.items():
            status = "✅ 성공 (자동화 가능)" if success else "❌ 실패 (수동 설정 필요)"
            print(f" - {ex.capitalize()}: {status}")
        print("==========================================")

if __name__ == "__main__":
    tester = MarketInfoTester()
    tester.run()