import asyncio
import logging
import sys
import os
import json
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Lighter] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("LighterTester")

# 환경변수 로드
load_dotenv()

try:
    import settings
    from exchange_apis import LighterExchange
    import lighter # SDK 직접 임포트 (잔고 조회용)
except ImportError as e:
    log.error(f"❌ 필수 모듈 로드 실패: {e}")
    print("   (pip install lighter-python python-dotenv 가 필요합니다)")
    sys.exit(1)

class LighterTester:
    def __init__(self):
        self.api_key = os.getenv("LIGHTER_PRIVATE_KEY")
        self.public_key = os.getenv("LIGHTER_WALLET_ADDRESS")
        
        if not self.api_key or not self.public_key:
            log.error("❌ .env에 LIGHTER_PRIVATE_KEY 또는 LIGHTER_WALLET_ADDRESS가 없습니다.")
            sys.exit(1)
            
        # 거래소 객체 생성
        self.exchange = LighterExchange(api_key=self.api_key, public_key=self.public_key)

    async def initialize(self):
        log.info("⏳ Lighter 연결 및 마켓 정보 로딩...")
        
        # load_markets 내부에서 '스마트 초기화'로 계정 인덱스(288085)를 찾고 클라이언트를 설정함
        await self.exchange.load_markets()
        
        if not self.exchange.client:
            log.error("❌ 클라이언트 초기화 실패. (지갑 주소나 키를 확인해주세요)")
            sys.exit(1)
            
        # 연결된 계정 정보 출력
        acc_idx = self.exchange.client.account_index
        log.info(f"✅ 초기화 완료 (Account Index: {acc_idx})")

    async def print_balance(self):
        """
        계정의 담보금(Collateral) 및 상세 정보를 조회합니다.
        """
        try:
            log.info("🔍 계정 자산 정보 조회 중...")
            
            # Exchange 내부의 api_client를 재사용
            account_api = lighter.AccountApi(self.exchange.api_client)
            
            # 계정 인덱스로 조회 (API 문서: GET /account?by=index&value=...)
            acc_idx = self.exchange.client.account_index
            
            account_info = await account_api.account(
                by="index", 
                value=str(acc_idx)
            )
            
            # 결과 출력
            print(f"\n📊 [계정 정보 (Index: {acc_idx})]")
            
            # account_info는 DetailedAccounts 객체일 수 있음
            # SDK 모델에 따라 속성 접근 방식이 다를 수 있어 안전하게 처리
            if hasattr(account_info, 'accounts') and account_info.accounts:
                # 리스트 형태인 경우 첫 번째 계정 정보
                acc_data = account_info.accounts[0]
            elif isinstance(account_info, list) and len(account_info) > 0:
                acc_data = account_info[0]
            else:
                acc_data = account_info

            # 속성 출력
            # (curl 결과: collateral, available_balance 등이 있음)
            collateral = getattr(acc_data, 'collateral', 'N/A')
            available = getattr(acc_data, 'available_balance', 'N/A')
            
            print(f"   💰 총 담보금 (Collateral): {collateral}")
            print(f"   💵 주문 가능 (Available): {available}")
            
            # 포지션 정보가 있다면 출력
            if hasattr(acc_data, 'positions'):
                print(f"   📈 포지션 현황:")
                for pos in acc_data.positions:
                    # 포지션 크기가 0이 아닌 것만 출력
                    size = float(getattr(pos, 'position', 0))
                    if size != 0:
                        sym = getattr(pos, 'symbol', 'Unknown')
                        side = "LONG" if getattr(pos, 'sign', 0) == 1 else "SHORT"
                        entry = getattr(pos, 'avg_entry_price', 0)
                        print(f"      - {sym}: {side} {size} (Entry: {entry})")
            else:
                print("   (포지션 정보 없음)")

        except Exception as e:
            log.error(f"❌ 잔고 조회 실패: {e}")

    async def place_order(self, side: str, symbol: str, amount: float):
        try:
            log.info(f"🚀 {symbol} {side} {amount} 주문 시도...")
            # Exchange 클래스의 place_market_order 사용
            res = await self.exchange.place_market_order(symbol, side, amount)
            
            if res:
                print(f"✅ 주문 성공: {res}")
                # 주문 후 잔고 갱신
                await asyncio.sleep(1)
                await self.print_balance()
            else:
                print("❌ 주문 실패 (로그 확인)")
        except Exception as e:
            log.error(f"❌ 주문 중 에러: {e}")

    async def set_leverage(self, symbol: str, leverage: int):
        log.info(f"⚙️ {symbol} 레버리지 {leverage}배 설정 시도...")
        res = await self.exchange.set_leverage(symbol, leverage)
        if res:
            print(f"✅ 설정 성공")
        else:
            print(f"❌ 설정 실패")

    async def run_console(self):
        await self.initialize()
        
        print("\n==================================")
        print("🕯️ Lighter Trading Tester")
        print("==================================")
        print("명령어 예시:")
        print(" - 잔고")
        print(" - 레버리지 ETH 10")
        print(" - 매수 ETH 0.01")
        print(" - 매도 ETH 0.01")
        print(" - exit")
        print("==================================\n")

        while True:
            try:
                cmd = await asyncio.get_running_loop().run_in_executor(None, input, ">> 입력: ")
                parts = cmd.strip().split()
                if not parts: continue
                
                action = parts[0]
                
                if action == 'exit': break
                elif action == '잔고':
                    await self.print_balance()
                elif action == '레버리지' and len(parts) == 3:
                    await self.set_leverage(parts[1].upper(), int(parts[2]))
                elif action in ['매수', '매도'] and len(parts) == 3:
                    side = 'BUY' if action == '매수' else 'SELL'
                    await self.place_order(side, parts[1].upper(), float(parts[2]))
                else:
                    print("⚠️ 알 수 없는 명령어입니다.")
            except Exception as e:
                log.error(f"오류 발생: {e}")

if __name__ == "__main__":
    try:
        tester = LighterTester()
        asyncio.run(tester.run_console())
    except KeyboardInterrupt:
        print("\n종료합니다.")