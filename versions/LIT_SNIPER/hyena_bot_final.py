import asyncio
import logging
import os
import math
from dotenv import load_dotenv
from hyperliquid.utils import constants as hl_constants
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange as HLExchange
from eth_account import Account

# --- 설정 섹션 ---
# 로그에서 확인된 HyENA DEX의 ID (Name)
HYENA_DEX_ID = "hyna" 

# HyENA 포인트 적립을 위한 빌더 주소
HYENA_BUILDER_ADDRESS = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
HYENA_BUILDER_FEE = 0

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("HyENA_Bot")

class HyenaBot:
    def __init__(self, private_key: str):
        self.account = Account.from_key(private_key)
        self.main_address = self.account.address
        # HyENA DEX의 인덱스를 찾기 위해 API 호출
        self.dex_index = self._find_dex_index(HYENA_DEX_ID)
        
        try:
            # 1. Info 객체 초기화 (HyENA DEX ID를 리스트로 전달)
            # SDK는 이 dex_index를 내부적으로 사용하여 HIP-3 자산을 매핑합니다.
            self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True, perp_dexs=[HYENA_DEX_ID])
            
            # 2. Exchange 객체 초기화
            self.exchange = HLExchange(
                self.account, 
                hl_constants.MAINNET_API_URL, 
                perp_dexs=[HYENA_DEX_ID] 
            )
            
            log.info(f"🦁 [HyENA] 봇 초기화 성공 (ID: {HYENA_DEX_ID}, Index: {self.dex_index})")
            log.info(f"   - 지갑: {self.main_address[:8]}...")
            
            # 3. 정밀도(Decimals) 정보 로드
            self.sz_decimals = {}
            self._load_precision()
            
        except Exception as e:
            log.error(f"❌ 초기화 중 치명적 오류: {e}")
            raise e

    def _find_dex_index(self, target_name):
        """DEX 이름으로 인덱스 번호를 찾습니다 (API 로직 보완)"""
        temp_info = Info(skip_ws=True)
        dexs = temp_info.perp_dexs()
        for i, dex in enumerate(dexs):
            if dex and dex.get('name') == target_name:
                return i
        # 못 찾으면 기본값 4 (로그 기준) 반환하거나 에러
        log.warning(f"⚠️ API 목록에서 '{target_name}'을 직접 찾지 못했습니다. (로그 기준 4로 가정)")
        return 4 

    def _load_precision(self):
        """서버에서 자산별 소수점 자릿수(szDecimals) 가져오기"""
        try:
            # 해당 DEX의 메타데이터 조회
            meta = self.info.meta(dex=HYENA_DEX_ID)
            for asset in meta['universe']:
                self.sz_decimals[asset['name']] = asset['szDecimals']
            log.info(f"✅ 마켓 데이터 로드 완료 ({len(self.sz_decimals)}개 심볼)")
            # LIT가 있는지 확인
            if "LIT" in self.sz_decimals:
                log.info(f"🔫 타겟 발견: LIT (Decimals: {self.sz_decimals['LIT']})")
            else:
                log.info("⏳ 타겟 대기중: LIT 아직 상장 안됨")
        except Exception as e:
            log.error(f"⚠️ 마켓 데이터 로드 실패: {e}")

    async def get_usde_balance(self):
        """USDe 잔고 조회 (HIP-3 DEX 전용)"""
        try:
            # dex 인자에 ID(문자열)를 넣으면 해당 DEX의 상태 조회
            state = self.info.user_state(self.main_address, dex=HYENA_DEX_ID)
            
            # HIP-3 DEX는 marginSummary에 해당 DEX의 담보(USDe) 정보가 있음
            margin = state.get('marginSummary', {})
            equity = float(margin.get('accountValue', 0))
            withdrawable = float(margin.get('withdrawable', 0))
            
            log.info(f"💰 [HyENA 잔고] 자산가치: ${equity:.2f} | 출금가능: ${withdrawable:.2f} (USDe)")
            return equity
        except Exception as e:
            log.error(f"❌ 잔고 조회 실패: {e}")
            return 0.0

    async def place_order(self, symbol: str, side: str, usd_amount: float):
        """
        주문 실행 함수 (자동 계산 및 정밀도 보정)
        """
        is_buy = (side.upper() == 'BUY')
        
        # 1. 현재가 조회 (HyENA 마켓 기준)
        mids = self.info.all_mids(dex=HYENA_DEX_ID)
        price = float(mids.get(symbol, 0))
        
        if price == 0:
            # 가격이 0이면 상장 전이거나 데이터 수신 실패
            # 스나이핑 모드에서는 로그를 줄이고 리턴
            # log.debug(f"{symbol} 가격 없음") 
            return False

        # 2. 수량 계산 (총 가치 / 현재가)
        raw_sz = usd_amount / price
        
        # 3. 정밀도 보정 (szDecimals)
        # 정보를 못 가져왔으면 기본값 2 사용
        decimals = self.sz_decimals.get(symbol, 2) 
        final_sz = round(raw_sz, decimals)
        
        if final_sz == 0:
            return False

        # 4. 가격 설정 (IOC 주문: 매수는 5% 위, 매도는 5% 아래)
        limit_px = price * 1.05 if is_buy else price * 0.95
        limit_px = float(f"{limit_px:.5g}") # 유효숫자 5자리

        log.info(f"🚀 주문 시도: {symbol} {side} {final_sz}개 @ ${limit_px} (현재가: ${price})")

        # 5. 주문 페이로드 구성
        order_request = {
            "coin": symbol,
            "is_buy": is_buy,
            "sz": final_sz,
            "limit_px": limit_px,
            "order_type": {"limit": {"tif": "Ioc"}}, # 즉시 체결 조건
            "reduce_only": False
        }

        try:
            # Builder Code 적용하여 주문 전송
            res = self.exchange.bulk_orders(
                [order_request], 
                builder={"b": HYENA_BUILDER_ADDRESS.lower(), "f": HYENA_BUILDER_FEE}
            )
            
            if res['status'] == 'ok':
                status = res['response']['data']['statuses'][0]
                if 'filled' in status:
                    fill = status['filled']
                    log.info(f"🎉 체결 완료! {symbol}: {fill['totalSz']}개 @ ${fill['avgPx']}")
                    return True
                elif 'error' in status:
                    # 잔고 부족 등의 에러 처리
                    err_msg = status['error']
                    if "Insufficient margin" in err_msg:
                        log.warning(f"⚠️ 주문 실패: 잔고 부족 (USDe 확인 필요)")
                    else:
                        log.warning(f"⚠️ 주문 거부: {err_msg}")
            else:
                log.error(f"❌ 응답 오류: {res}")
                
        except Exception as e:
            # Asset not found는 상장 전 흔한 에러이므로 무시 가능
            if "Asset not found" not in str(e):
                log.error(f"❌ 주문 예외: {e}")
        
        return False

# --- 메인 실행부 ---
async def main():
    load_dotenv()
    pk = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    if not pk:
        print("❌ .env 파일 확인 필요")
        return

    bot = HyenaBot(pk)
    
    # 1. 잔고 확인 (USDe가 보여야 성공)
    print("\n--- [1단계] USDe 잔고 확인 ---")
    await bot.get_usde_balance()
    
    # 2. LIT 스나이핑 루프 (무한 반복)
    print("\n--- [2단계] LIT 스나이핑 시작 ---")
    print("   (LIT가 상장되어 가격이 뜨는 순간 주문이 들어갑니다)")
    
    target_usd = 20.0 # 주문할 금액 ($20)
    
    while True:
        # LIT 매수 시도 (가격이 없으면 내부에서 무시됨)
        # 상장되면 즉시 매수
        success = await bot.place_order("LIT", "BUY", target_usd)
        
        if success:
            print("✨ 스나이핑 성공! 프로그램을 종료합니다.")
            break
            
        # 너무 빠른 루프 방지 (0.1초 ~ 0.5초 권장)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())