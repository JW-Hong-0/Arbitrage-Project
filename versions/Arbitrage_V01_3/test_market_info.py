import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# 사용자 환경에 맞게 경로 설정 (필요시)
# sys.path.append("...") 

from exchange_apis import HyperliquidExchange, GrvtExchange

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("Tester")

async def test_market_data():
    load_dotenv()
    
    log.info("🚀 거래소 시장 데이터 검증 시작...")
    
    # 1. 거래소 인스턴스 생성 (API Key는 .env에서 로드된다고 가정)
    hl = HyperliquidExchange()
    grvt = GrvtExchange() # .env 내부의 GRVT_API_KEY 등을 사용하도록 구현되어 있어야 함

    # 2. 시장 데이터 로드 (병렬 실행)
    log.info("📡 API 요청 보내는 중...")
    await asyncio.gather(
        hl.load_markets(),
        grvt.load_markets()
    )

    # 3. 결과 출력 및 검증
    target_coins = ['BTC', 'ETH', 'SOL', 'XRP'] # 확인하고 싶은 코인들
    
    print("\n" + "="*80)
    print(f"{'Exchange':<12} | {'Coin':<5} | {'Qty Prec':<10} | {'Min Size':<12} | {'Price Prec':<10} | {'Test 0.12345'}")
    print("-" * 80)

    for coin in target_coins:
        # Hyperliquid Check
        hl_info = hl.market_info.get(coin)
        if hl_info:
            test_val = hl.validate_amount(coin, 0.12345678)
            print(f"{'Hyperliquid':<12} | {coin:<5} | {hl_info['qty_prec']:<10} | {hl_info['min_size']:<12} | {hl_info['price_prec']:<10} | {test_val}")
        else:
            print(f"{'Hyperliquid':<12} | {coin:<5} | {'N/A':<10} | {'N/A':<12} | {'N/A':<10} | -")

        # GRVT Check
        grvt_info = grvt.market_info.get(coin)
        if grvt_info:
            test_val = grvt.validate_amount(coin, 0.12345678)
            print(f"{'GRVT':<12} | {coin:<5} | {grvt_info['qty_prec']:<10} | {grvt_info['min_size']:<12} | {grvt_info['price_prec']:<10} | {test_val}")
        else:
            print(f"{'GRVT':<12} | {coin:<5} | {'N/A':<10} | {'N/A':<12} | {'N/A':<10} | -")
        
        print("-" * 80)

    print("\n✅ 테스트 완료. 위 테이블에서 'Qty Prec'(자릿수)와 'Test' 결과값이 잘 잘리는지 확인하세요.")
    print("예: ETH의 GRVT Qty Prec가 2라면, Test 값은 0.12 여야 합니다 (0.123 아님).")

if __name__ == "__main__":
    asyncio.run(test_market_data())