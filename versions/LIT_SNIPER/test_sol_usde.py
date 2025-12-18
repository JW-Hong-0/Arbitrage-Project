import asyncio
import os
import time
from dotenv import load_dotenv
from hyena_exchange import HyenaExchange

load_dotenv()

async def test_sol_leverage():
    pk = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    bot = HyenaExchange(pk)
    
    SYMBOL = "SOL"
    LEVERAGE = 3
    POSITION_VALUE_USD = 20.0 # 목표 포지션 가치 ($20)

    print(f"\n--- 1. {SYMBOL} 레버리지 {LEVERAGE}배 설정 ---")
    await bot.set_leverage(SYMBOL, LEVERAGE)

    print(f"\n--- 2. 현재가 조회 및 수량 계산 ---")
    # Hyperliquid Info 객체 사용
    all_mids = bot.info.all_mids()
    price = float(all_mids.get(SYMBOL, 0))
    
    if price == 0:
        print("❌ 가격 조회 실패")
        return

    # 수량 = 목표가치 / 현재가 (레버리지 적용된 가치가 $20이 되도록)
    # 예: SOL $150, 20불치 = 0.133 SOL
    buy_amount = POSITION_VALUE_USD / price
    print(f"Current Price: ${price}")
    print(f"Target Value: ${POSITION_VALUE_USD} (Lev {LEVERAGE}x)")
    print(f"Order Amount: {buy_amount:.4f} {SYMBOL}")

    # 실제 증거금 필요액은 약 $6.67 (20 / 3)
    
    print(f"\n--- 3. 주문 실행 (Long) ---")
    # 시장가 효과를 위해 현재가보다 1% 높게 잡고 IOC 주문
    limit_price = price * 1.01
    
    success = await bot.place_hyena_perp_order(
        SYMBOL, "BUY", buy_amount, limit_price
    )
    
    if success:
        print("\n🎉 테스트 성공: 포지션 진입 완료")
        print("⚠️ 3초 후 포지션을 종료합니다...")
        await asyncio.sleep(3)
        
        print("\n--- 4. 포지션 종료 (청산) ---")
        # 현재 포지션 크기만큼 매도 (Reduce Only 아님, 단순 매도로 청산)
        # 시장가 매도 효과 (현재가 * 0.99)
        close_price = price * 0.99
        await bot.place_hyena_perp_order(SYMBOL, "SELL", buy_amount, close_price, reduce_only=True)
        print("✅ 포지션 종료 시도 완료")

if __name__ == "__main__":
    asyncio.run(test_sol_leverage())