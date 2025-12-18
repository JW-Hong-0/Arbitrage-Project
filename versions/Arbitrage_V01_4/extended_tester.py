import asyncio
import logging
import sys
import os
from decimal import Decimal
from dotenv import load_dotenv

# SDK Imports
try:
    from x10.perpetual.accounts import StarkPerpetualAccount
    from x10.perpetual.configuration import MAINNET_CONFIG
    from x10.perpetual.orders import OrderSide, TimeInForce
    from x10.perpetual.simple_client.simple_trading_client import BlockingTradingClient
    # [추가] 조회용 모듈 임포트
    from x10.perpetual.trading_client.account_module import AccountModule
except ImportError:
    print("❌ Extended SDK(x10)를 찾을 수 없습니다.")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Extended] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("ExtendedTester")
load_dotenv()

class ExtendedTester:
    def __init__(self):
        self.api_key = os.getenv("EXTENDED_API_KEY")
        self.public_key = os.getenv("EXTENDED_PUBLIC_KEY")
        self.private_key = os.getenv("EXTENDED_PRIVATE_KEY")
        self.vault = int(os.getenv("EXTENDED_VAULT") or "100001")
        
        if not all([self.api_key, self.public_key, self.private_key]):
            log.error("❌ .env에 EXTENDED 관련 설정이 부족합니다.")
            sys.exit(1)

        self.client = None # 주문용 (BlockingTradingClient)
        self.info_client = None # 조회용 (AccountModule)
        self.account = None

    async def initialize(self):
        log.info("⏳ Extended 클라이언트 연결 중...")
        try:
            # 계정 객체 생성
            self.account = StarkPerpetualAccount(
                vault=self.vault,
                private_key=self.private_key,
                public_key=self.public_key,
                api_key=self.api_key,
            )
            
            # 1. 주문용 클라이언트 (Simple Client)
            self.client = await BlockingTradingClient.create(
                endpoint_config=MAINNET_CONFIG, 
                account=self.account
            )
            
            # 2. 조회용 모듈 (Account Module) 직접 초기화
            # AccountModule은 (config, api_key)를 받습니다.
            self.info_client = AccountModule(
                endpoint_config=MAINNET_CONFIG,
                api_key=self.api_key
            )
            
            log.info("✅ 연결 성공")
        except Exception as e:
            log.error(f"❌ 연결 실패: {e}")
            sys.exit(1)

    async def print_balance(self):
        try:
            # 1. 잔고 조회
            log.info("🔍 잔고 조회 중...")
            balance_resp = await self.info_client.get_balance()
            if balance_resp.data:
                b = balance_resp.data
                print(f"\n💰 [잔고 정보]")
                print(f"   - Equity: {b.equity}")
                print(f"   - Available: {b.available_for_trade}")
                print(f"   - PnL: {b.unrealised_pnl}")
            
            # 2. 포지션 조회
            log.info("🔍 포지션 조회 중...")
            pos_resp = await self.info_client.get_positions()
            
            print("\n📊 [포지션 목록]")
            if pos_resp.data:
                for pos in pos_resp.data:
                    # 필드명은 SDK 모델(PositionModel) 참고 (size, side, market 등)
                    print(f"   - {pos.market}: {pos.side} {pos.size} (Entry: {pos.open_price})")
            else:
                print("   (보유 포지션 없음)")

        except Exception as e:
            log.error(f"❌ 조회 실패: {e}")

    async def place_order(self, side_str: str, symbol: str, amount: float):
        try:
            market_name = f"{symbol}-USD"
            markets = await self.client.get_markets()
            
            if market_name not in markets:
                log.error(f"❌ 마켓 미지원: {market_name}")
                return

            market = markets[market_name]
            side = OrderSide.BUY if side_str == 'BUY' else OrderSide.SELL
            
            # [수정] 슬리피지를 5% -> 3%로 축소 (Price Band 준수)
            # 실제 현재가를 모르므로 임시 가격(dummy_price)을 쓸 때는 주의 필요
            # 여기서는 직전 체결가(Entry Price)를 참고하거나, 
            # 사용자가 입력한 가격을 쓰는 게 좋지만, 테스트용이므로 슬리피지만 줄임.
            
            current_price = 3055 # 방금 체결된 가격 참고
            slippage = Decimal("0.03") # 3%
            
            price = Decimal(str(current_price)) * (1 + slippage) if side == OrderSide.BUY else Decimal(str(current_price)) * (1 - slippage)
            rounded_price = market.trading_config.round_price(price)
            
            qty = Decimal(str(amount))
            
            log.info(f"🚀 주문 전송: {market_name} {side_str} {qty} @ {rounded_price}")
            
            order = await self.client.create_and_place_order(
                amount_of_synthetic=qty,
                price=rounded_price,
                market_name=market.name,
                side=side,
                post_only=False,
                time_in_force=TimeInForce.IOC,
            )
            print(f"✅ 주문 결과: {order}")
            
        except Exception as e:
            log.error(f"❌ 주문 에러: {e}")

    async def run_console(self):
        await self.initialize()
        print("\n🦅 Extended Tester Ready")
        print("명령: 잔고 / 매수 ETH 0.01 / 매도 ETH 0.01 / exit")
        
        while True:
            try:
                cmd = await asyncio.get_running_loop().run_in_executor(None, input, ">> ")
                parts = cmd.strip().split()
                if not parts: continue
                
                if parts[0] == 'exit': break
                elif parts[0] == '잔고': await self.print_balance()
                elif parts[0] in ['매수', '매도'] and len(parts) == 3:
                    await self.place_order(parts[0] == '매수' and 'BUY' or 'SELL', parts[1].upper(), float(parts[2]))
                else: print("⚠️ 명령 오류")
            except Exception as e:
                log.error(f"Error: {e}")
        
        await self.client.close()

if __name__ == "__main__":
    asyncio.run(ExtendedTester().run_console())