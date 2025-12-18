import asyncio
import sys
import logging
import os
import json

# --- 1. 설정 로드 ---
try:
    import settings
    from exchange_apis import HyperliquidExchange
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as e:
    print(f"❌ 임포트 실패: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [TESTER] - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("API_Tester")

async def main():
    # --- 2. 키 로드 ---
    priv_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    main_addr = os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS")
    
    if not priv_key or not main_addr:
        logger.error("❌ .env 설정 오류: Private Key 또는 Main Address 누락")
        return

    # --- 3. 거래소 인스턴스 생성 ---
    logger.info("🔌 거래소 연결 중...")
    exchange = HyperliquidExchange(private_key=priv_key, main_address=main_addr)
    
    # ----------------------------------------------------
    # 사용자 명령 루프
    # ----------------------------------------------------
    print("\n✅ 통합 테스트 준비 완료 (대상: ETH)")
    print("명령어: '잔고', '매수 10', '매도 10', '청산', 'exit'")
    
    while True:
        loop = asyncio.get_running_loop()
        cmd = await loop.run_in_executor(None, input, "\n>> 명령 입력: ")
        cmd = cmd.strip()
        
        if not cmd: continue
        if cmd == "exit": break
        
        # 1. 잔고 확인
        if cmd == "잔고":
            balance = await exchange.get_balance()
            if balance:
                print(f"\n💰 총 자산 (Equity): ${balance['equity']:,.2f}")
                print(f"💵 출금 가능 (Withdrawable): ${balance['withdrawable']:,.2f}")
                
                # 포지션 요약 출력
                positions = balance['raw'].get('assetPositions', [])
                found_eth = False
                for p in positions:
                    pos = p['position']
                    coin = pos['coin']
                    size = float(pos['szi'])
                    if size != 0:
                        side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                        print(f"   - {coin}: {side} {size} (Entry: ${float(pos['entryPx']):,.2f})")
                        if coin == "ETH": found_eth = True
                
                if not found_eth:
                    print("   - ETH 포지션 없음")
            else:
                logger.error("잔고 조회 실패")

        # 2. 매수 (ETH)
        elif cmd.startswith("매수"):
            try:
                # 입력: "매수 10" (USD 기준)
                usd_amount = float(cmd.split()[1])
                
                # 현재가 조회 (allMids)
                mids = exchange.info.all_mids()
                price = float(mids.get("ETH", 0))
                
                if price > 0:
                    # 수량 계산 (USD / Price)
                    qty = usd_amount / price
                    
                    # 넉넉한 슬리피지(5%)를 둔 시장가성 주문
                    limit_px = price * 1.05
                    
                    res = await exchange.create_order("ETH", "BUY", limit_px, qty)
                    
                    if res and res['status'] == 'ok':
                        statuses = res['response']['data']['statuses']
                        if statuses and 'error' in statuses[0]:
                            logger.error(f"❌ 주문 실패: {statuses[0]}")
                        else:
                            logger.info(f"✅ ETH 매수 성공! (${usd_amount} 규모)")
                    else:
                        logger.error(f"주문 전송 에러: {res}")
                else:
                    logger.error("ETH 가격 조회 실패")
            except Exception as e:
                logger.error(f"명령어 오류: {e}")

        # 3. 매도 (ETH)
        elif cmd.startswith("매도"):
            try:
                usd_amount = float(cmd.split()[1])
                mids = exchange.info.all_mids()
                price = float(mids.get("ETH", 0))
                
                if price > 0:
                    qty = usd_amount / price
                    limit_px = price * 0.95 # 5% 아래로 던짐
                    
                    res = await exchange.create_order("ETH", "SELL", limit_px, qty)
                    
                    if res and res['status'] == 'ok':
                        statuses = res['response']['data']['statuses']
                        if statuses and 'error' in statuses[0]:
                            logger.error(f"❌ 주문 실패: {statuses[0]}")
                        else:
                            logger.info(f"✅ ETH 매도 성공! (${usd_amount} 규모)")
                    else:
                        logger.error(f"주문 전송 에러: {res}")
                else:
                    logger.error("ETH 가격 조회 실패")
            except Exception as e:
                logger.error(f"명령어 오류: {e}")

        # 4. 청산 (ETH)
        elif cmd == "청산":
            logger.info("🚨 ETH 포지션 청산 시도...")
            res = await exchange.close_position("ETH")
            
            if res:
                if res['status'] == 'ok':
                    statuses = res['response']['data']['statuses']
                    if statuses and 'error' in statuses[0]:
                        logger.error(f"❌ 청산 실패: {statuses[0]}")
                    else:
                        logger.info("✅ ETH 청산 완료!")
                else:
                    logger.error(f"청산 주문 에러: {res}")
            else:
                logger.info("청산할 ETH 포지션이 없거나 에러 발생")

if __name__ == "__main__":
    asyncio.run(main())