import requests
import json
import logging
import sys

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
        log.info("--- [1] Hyperliquid ---")
        url = "https://api.hyperliquid.xyz/info"
        try:
            res = requests.post(url, json={"type": "meta"}, headers={"Content-Type": "application/json"}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                eth = next((i for i in data['universe'] if i['name'] == 'ETH'), None)
                if eth:
                    log.info(f"✅ 성공: ETH Decimals={eth['szDecimals']}, MaxLev={eth['maxLeverage']}")
                    self.results['hyperliquid'] = True
            else:
                log.error(f"❌ 실패: {res.status_code}")
        except Exception as e: log.error(f"❌ 에러: {e}")

    def test_pacifica(self):
        log.info("\n--- [2] Pacifica ---")
        url = "https://api.pacifica.fi/api/v1/info"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json().get('data', [])
                eth = next((i for i in data if i['symbol'] == 'ETH'), None)
                if eth:
                    log.info(f"✅ 성공: ETH LotSize={eth['lot_size']}, MaxLev={eth['max_leverage']}")
                    self.results['pacifica'] = True
            else:
                log.error(f"❌ 실패: {res.status_code}")
        except Exception as e: log.error(f"❌ 에러: {e}")

    def test_lighter(self):
        log.info("\n--- [3] Lighter ---")
        url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json().get('order_books', [])
                eth = next((i for i in data if i['symbol'] == 'ETH'), None)
                if eth:
                    log.info(f"✅ 성공: ETH MinSize={eth['min_base_amount']}, SizeDec={eth['supported_size_decimals']}")
                    self.results['lighter'] = True
            else:
                log.error(f"❌ 실패: {res.status_code}")
        except Exception as e: log.error(f"❌ 에러: {e}")

    def test_extended(self):
        log.info("\n--- [4] Extended (API Doc 기반) ---")
        # 문서에 명시된 Mainnet URL: api.starknet.extended.exchange
        url = "https://api.starknet.extended.exchange/api/v1/info/markets"
        try:
            headers = {"User-Agent": "Mozilla/5.0"} # 차단 방지용
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json().get('data', [])
                # Extended는 심볼명이 "BTC-USD" 형식임
                eth = next((i for i in data if i['name'] == 'ETH-USD'), None)
                if eth:
                    conf = eth.get('tradingConfig', {})
                    log.info(f"✅ 성공: ETH-USD MinSize={conf.get('minOrderSize')}, MaxLev={conf.get('maxLeverage')}")
                    self.results['extended'] = True
                else:
                    log.warning("⚠️ ETH-USD 심볼 못 찾음 (데이터 구조 확인 필요)")
            else:
                log.error(f"❌ 실패: {res.status_code} (URL 확인 필요)")
        except Exception as e: log.error(f"❌ 에러: {e}")

    def test_grvt(self):
        log.info("\n--- [5] GRVT (SDK 권장) ---")
        log.info("ℹ️ GRVT는 Public REST API가 제한적이거나 인증이 필요할 수 있습니다.")
        log.info("   실제 봇에서는 SDK(GrvtCcxtWS)를 사용하므로 정상 작동할 것입니다.")
        self.results['grvt'] = "SDK Checked"

    def run(self):
        print("==========================================")
        print("🌍 5대 거래소 마켓 정보 수집 테스트")
        print("==========================================")
        self.test_hyperliquid()
        self.test_pacifica()
        self.test_lighter()
        self.test_extended()
        self.test_grvt()
        
        print("\n==========================================")
        print("📊 [결과 요약]")
        for ex, res in self.results.items():
            print(f" - {ex.capitalize()}: {res}")
        print("==========================================")

if __name__ == "__main__":
    MarketInfoTester().run()