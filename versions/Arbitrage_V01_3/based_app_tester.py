import asyncio
import sys
import logging
import json
import os
import traceback
import math

# --- Hyperliquid SDK ---
from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils.types import Cloid
from eth_account import Account

# --- 설정 로드 ---
try:
    import settings
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("❌ settings.py 또는 .env 파일을 찾을 수 없습니다.")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [TESTER] - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BasedAppTester")

# --- Based App 상수 ---
BASED_BUILDER_ADDRESS = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
BASED_BUILDER_FEE = 25
BASED_CLOID_STR = "0xba5ed11067f2cc08ba5ed10000ba5ed1"

class BasedAppTester:
    def __init__(self):
        # 1. 서명용 계정 (Agent Private Key)
        self.private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        if not self.private_key:
            logger.error("❌ .env에 HYPERLIQUID_PRIVATE_KEY가 없습니다.")
            sys.exit(1)
        
        self.account = Account.from_key(self.private_key)
        self.agent_address = self.account.address

        # 2. 조회용 주소 (Master Wallet Address)
        self.main_address = os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS")
        
        if not self.main_address:
            print(f"\n⚠️ [경고] 'HYPERLIQUID_MAIN_WALLET_ADDRESS'가 설정되지 않았습니다.")
            self.main_address = self.agent_address
        
        logger.info(f"🔑 서명(Agent): {self.agent_address}")
        logger.info(f"💰 본체(Vault): {self.main_address}")

        # 3. SDK 초기화
        self.info = Info(base_url=constants.MAINNET_API_URL, skip_ws=True)
        
        # Agent 사용 시 vault_address 제거 (일반 계정 매매)
        self.exchange = Exchange(
            self.account, 
            base_url=constants.MAINNET_API_URL
        )
        
        self.meta = self.info.meta()
        self.coin_map = {a['name']: a for a in self.meta['universe']}
        logger.info("✅ API 연결 및 객체 초기화 완료")

    async def get_btc_price(self):
        all_mids = self.info.all_mids()
        return float(all_mids.get("BTC", 0))

    def _get_sz_decimals(self, coin="BTC"):
        return self.coin_map[coin]['szDecimals']

    def _round_sz(self, size, coin="BTC"):
        decimals = self._get_sz_decimals(coin)
        return round(size, decimals)

    def _round_px(self, price):
        """
        Hyperliquid 가격 규격: 유효숫자 5자리 (5 Significant Figures)
        예: 97447.88 -> 97448 (5자리)
            0.123456 -> 0.12346 (5자리)
        """
        if price == 0: return 0.0
        # 유효숫자 5자리로 포맷팅 후 다시 float으로 변환하여 불필요한 소수점 제거
        return float(f"{price:.5g}")

    async def print_status(self):
        """잔고 및 포지션 조회"""
        logger.info(f"📊 상태 조회 중... (Target: {self.main_address})")
        try:
            user_state = self.info.user_state(self.main_address)
            margin_summary = user_state.get('marginSummary', {})
            positions = user_state.get('assetPositions', [])
            
            balance = float(margin_summary.get('accountValue', 0))
            withdrawable = float(margin_summary.get('withdrawable', 0))
            
            print(f"\n======== [ 내 자산 현황 ({self.main_address[:6]}...) ] ========")
            print(f"💰 총 자산 가치 : ${balance:,.2f}")
            print(f"💵 출금 가능액  : ${withdrawable:,.2f}")
            print(f"======================================================")

            has_pos = False
            for p in positions:
                pos = p.get('position', {})
                coin = pos.get('coin')
                size = float(pos.get('szi', 0))
                entry_px = float(pos.get('entryPx', 0))
                pnl = float(pos.get('unrealizedPnl', 0))
                
                if size != 0:
                    has_pos = True
                    side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                    print(f"Coin: {coin:<5} | {side} | Size: {size} | Entry: ${entry_px:,.2f} | PnL: ${pnl:,.2f}")
            
            if not has_pos:
                print("보유 중인 포지션이 없습니다.")
            print("======================================================\n")

        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")

    async def place_order_usd(self, side_input, usd_amount):
        """BTC 주문"""
        coin = "BTC"
        is_buy = True if side_input == 'buy' else False
        
        try:
            price = await self.get_btc_price()
            if price == 0: return

            size = usd_amount / price
            size = self._round_sz(size, coin)
            
            if size == 0:
                logger.warning(f"수량이 너무 작습니다. (${usd_amount}) -> {size} BTC")
                return

            slippage = 0.05
            raw_limit_px = price * (1 + slippage) if is_buy else price * (1 - slippage)
            
            # [수정] 가격을 유효숫자 5자리로 반올림하여 API 오류 방지
            limit_px = self._round_px(raw_limit_px)

            cloid_obj = Cloid(BASED_CLOID_STR)

            order_request = {
                "coin": coin,
                "is_buy": is_buy,
                "sz": size,
                "limit_px": limit_px,
                "order_type": {"limit": {"tif": "Gtc"}},
                "reduce_only": False,
                "cloid": cloid_obj
            }

            logger.info(f"🚀 주문 전송: {coin} {'매수' if is_buy else '매도'} ${usd_amount} (Qty: {size}, Px: {limit_px})")

            result = self.exchange.bulk_orders(
                [order_request],
                builder={
                    "b": BASED_BUILDER_ADDRESS,
                    "f": BASED_BUILDER_FEE
                }
            )
            
            print("\n🔍 [DEBUG] 주문 결과:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("-" * 40)
            
            status = result['status']
            if status == 'ok':
                statuses = result['response']['data']['statuses']
                if statuses and 'error' in statuses[0]:
                    logger.error(f"❌ API 주문 거절: {statuses[0]}")
                else:
                    logger.info(f"✅ 주문 체결 성공!")
                    await self.print_status()
            else:
                logger.error(f"❌ 시스템 에러: {result}")

        except Exception as e:
            logger.error(f"주문 실행 중 오류 발생: {e}")
            # traceback.print_exc()

    async def close_all_btc(self):
        logger.info("🚨 BTC 포지션 청산 시도...")
        try:
            user_state = self.info.user_state(self.main_address)
            positions = user_state.get('assetPositions', [])
            btc_pos = next((p['position'] for p in positions if p['position']['coin'] == 'BTC'), None)
            
            if not btc_pos:
                logger.info("BTC 포지션이 없습니다.")
                return

            size = float(btc_pos['szi'])
            if size == 0: return

            is_buy = True if size < 0 else False 
            
            price = await self.get_btc_price()
            raw_limit_px = price * (1.05 if is_buy else 0.95)
            
            # [수정] 청산 가격도 반올림 적용
            limit_px = self._round_px(raw_limit_px)
            
            cloid_obj = Cloid(BASED_CLOID_STR)

            order_request = {
                "coin": "BTC",
                "is_buy": is_buy,
                "sz": abs(size),
                "limit_px": limit_px,
                "order_type": {"limit": {"tif": "Ioc"}}, 
                "reduce_only": True,
                "cloid": cloid_obj
            }
            
            result = self.exchange.bulk_orders(
                [order_request],
                builder={"b": BASED_BUILDER_ADDRESS, "f": BASED_BUILDER_FEE}
            )
            
            print("\n🔍 [DEBUG] 청산 결과:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if result['status'] == 'ok':
                 statuses = result['response']['data']['statuses']
                 if statuses and 'error' in statuses[0]:
                     logger.error(f"❌ 청산 주문 거절: {statuses[0]}")
                 else:
                     logger.info("✅ 청산 성공!")
                     await self.print_status()
            else:
                logger.error(f"❌ 청산 실패: {result}")

        except Exception as e:
            logger.error(f"청산 중 오류: {e}")

    async def run_console(self):
        print("\n🤖 Based App Tester (Agent Support)")
        print(f"🔑 Signer: {self.agent_address}")
        print(f"💰 Vault : {self.main_address}")
        
        while True:
            loop = asyncio.get_running_loop()
            cmd = await loop.run_in_executor(None, input, ">> 명령 (잔고/매수 10/매도 10/청산): ")
            cmd = cmd.strip()
            if not cmd: continue

            if cmd == "exit": break
            elif cmd == "잔고": await self.print_status()
            elif cmd.startswith("매수"):
                try: await self.place_order_usd('buy', float(cmd.split()[1]))
                except: print("형식: 매수 10")
            elif cmd.startswith("매도"):
                try: await self.place_order_usd('sell', float(cmd.split()[1]))
                except: print("형식: 매도 10")
            elif cmd == "청산": await self.close_all_btc()

async def main():
    tester = BasedAppTester()
    await tester.run_console()

if __name__ == "__main__":
    asyncio.run(main())