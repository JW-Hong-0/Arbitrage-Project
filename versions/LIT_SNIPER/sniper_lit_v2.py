import asyncio
import logging
import os
import random
import time
from dotenv import load_dotenv
from hyperliquid.utils import constants as hl_constants
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange as HLExchange
from eth_account import Account

# --- [설정 섹션] ---
HYENA_DEX_ID = "hyna"
TARGET_SYMBOL = "hyna:LIT"  # 타겟 티커 (실전: hyna:LIT)

# 주문 설정
LEVERAGE = 3
ORDER_SIZE_USD = 20.0    # 1회 주문당 $20 (레버리지 포함 가치)
PRICE_MIN = 3.0
PRICE_MAX = 5.0

# 반복 속도 (초)
INTERVAL = 0.2

# HyENA 빌더 정보
HYENA_BUILDER = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
HYENA_FEE = 0

# 로깅 설정 (깔끔한 출력을 위해 포맷 단순화)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger("SniperV2")

class HyenaSniperV2:
    def __init__(self):
        load_dotenv()
        self.pk = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        self.account = Account.from_key(self.pk)
        
        # HyENA 연결
        self.info = Info(hl_constants.MAINNET_API_URL, skip_ws=True, perp_dexs=[HYENA_DEX_ID])
        self.exchange = HLExchange(self.account, hl_constants.MAINNET_API_URL, perp_dexs=[HYENA_DEX_ID])
        
        self.sz_decimals = 2
        self.counters = {
            "total": 0,
            "success": 0,
            "fail": 0
        }

    def prepare(self):
        print(f"\n🔫 [연발 스나이퍼 장전 완료]")
        print(f"   - 타겟: {TARGET_SYMBOL}")
        print(f"   - 범위: ${PRICE_MIN} ~ ${PRICE_MAX}")
        print(f"   - 규모: 1회당 ${ORDER_SIZE_USD} (증거금 소진 시까지 반복)\n")
        
        # 마켓 정보 로드
        try:
            meta = self.info.meta(dex=HYENA_DEX_ID)
            for asset in meta['universe']:
                if asset['name'] == TARGET_SYMBOL:
                    self.sz_decimals = asset['szDecimals']
                    print(f"✅ 마켓 정보 로드: {TARGET_SYMBOL} (Decimals: {self.sz_decimals})")
                    break
        except Exception:
            print(f"⚠️ 마켓 정보 로드 실패 (기본값 사용). 상장 직전일 수 있음.")

        # 레버리지 설정 시도
        try:
            self.exchange.update_leverage(LEVERAGE, TARGET_SYMBOL, is_cross=True)
        except:
            pass

    async def run(self):
        print("🚀 스나이핑 시작... (Ctrl+C로 중단 가능)")
        
        while True:
            self.counters["total"] += 1
            current_try = self.counters["total"]
            
            # 1. 랜덤 가격 및 수량 계산
            limit_px = round(random.uniform(PRICE_MIN, PRICE_MAX), 4)
            
            # 수량 계산 (가격이 0이거나 미상장일 경우 대비 안전장치)
            # 여기서는 API 조회 없이 그냥 계산 (속도 최우선) -> 주문 실패 시 재시도
            raw_sz = ORDER_SIZE_USD / limit_px
            final_sz = round(raw_sz, self.sz_decimals)

            if final_sz <= 0:
                continue

            # 2. 로그 출력 (요청하신 포맷)
            log_msg = (
                f"[{current_try}번째] {TARGET_SYMBOL} ${limit_px} 주문 시도... "
                f"성공 {self.counters['success']}, 실패 {self.counters['fail']}"
            )
            print(log_msg)  # 한 줄씩 출력

            # 3. 주문 전송
            req = {
                "coin": TARGET_SYMBOL,
                "is_buy": True,
                "sz": final_sz,
                "limit_px": limit_px,
                "order_type": {"limit": {"tif": "Ioc"}},
                "reduce_only": False
            }

            try:
                res = self.exchange.bulk_orders(
                    [req], 
                    builder={"b": HYENA_BUILDER.lower(), "f": HYENA_FEE}
                )
                
                status = res['status']
                if status == 'ok':
                    data = res['response']['data']['statuses'][0]
                    
                    if 'filled' in data:
                        fill = data['filled']
                        self.counters["success"] += 1
                        print(f"   🎉 체결 확인! {fill['totalSz']}개 @ ${fill['avgPx']} (누적 성공: {self.counters['success']}회)")
                        
                        # [중요] 연발 모드: 성공해도 계속 돕니다.
                        # 단, 너무 빠르면 서버 부하가 있으니 최소한의 딜레이
                        # await asyncio.sleep(0.1) 
                        
                    elif 'error' in data:
                        err = data['error']
                        self.counters["fail"] += 1
                        
                        # [종료 조건] 잔고 부족 시 종료
                        if "Insufficient margin" in err:
                            print(f"\n🛑 증거금 부족으로 종료합니다. (총 {self.counters['success']}회 체결)")
                            break
                        
                        # Asset not found 등은 그냥 실패로 카운트하고 계속 진행
                        
                else:
                    self.counters["fail"] += 1

            except Exception as e:
                # 네트워크 에러 등은 무시하고 카운트만 증가
                self.counters["fail"] += 1
            
            # 속도 조절
            await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    sniper = HyenaSniperV2()
    sniper.prepare()
    asyncio.run(sniper.run())