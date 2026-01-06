import asyncio
import sys
import os
import logging
import time
import random
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN

# 1. 필터 클래스 정의
class GRVTFilter(logging.Filter):
    def filter(self, record):
        # 차단하고 싶은 키워드 리스트
        blacklist = ['get_signable_message', 'EIP712_ORDER_MESSAGE_TYPE', 'message_data', 'get_cookie_with_expiration']
        # 메시지에 블랙리스트 단어가 포함되어 있으면 False 반환 (출력 안 함)
        return not any(word in record.getMessage() for word in blacklist)

# 2. 로깅 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [FARMER] - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("volume_farmer.log", encoding='utf-8')
    ]
)

# 3. 루트 로거에 필터 적용 (모든 로그에 대해 검사)
for handler in logging.root.handlers:
    handler.addFilter(GRVTFilter())

log = logging.getLogger("VolumeFarmer")

# 기존 파일 임포트
try:
    from exchange_apis import HyperliquidExchange, GrvtExchange
    from utils.trade_sizer import TradeSizer  #
except ImportError:
    logging.error("❌ 필수 모듈(exchange_apis.py, trade_sizer.py)을 찾을 수 없습니다.")
    sys.exit(1)

# ==========================================
# ⚙️ 봇 설정 (Settings)
# ==========================================
SYMBOLS = ["BTC", "ETH"]      # 파밍 대상 코인
LEVERAGE = 10                 # 레버리지
MARGIN_PER_ASSET = 10.0       # 코인당 투입 증거금 ($20 x 10배 = $200 규모)

# 시간 설정 (단위: 초)
MIN_HOLD_SEC = 60             # 포지션 유지 (파밍) 최소 시간
MAX_HOLD_SEC = 600            # 포지션 유지 (파밍) 최대 시간
MIN_REST_SEC = 60             # 휴식 시간 최소
MAX_REST_SEC = 120            # 휴식 시간 최대

class VolumeFarmer:
    def __init__(self):
        load_dotenv()
        self.hl_key = os.getenv("HYPERLIQUID_PRIVATE_KEY") or os.getenv("HL_SECRET_KEY")
        if not self.hl_key:
            log.error("❌ .env 확인 필요")
            sys.exit(1)
        self.hl = None
        self.grvt = None
        self.sizer = None # 수량 최적화 도구

    async def initialize(self):
        log.info("🔌 거래소 연결 중...")
        self.hl = HyperliquidExchange(private_key=self.hl_key)
        self.grvt = GrvtExchange()
        
        log.info("📥 시장 데이터 로드 중...")
        await asyncio.gather(self.hl.load_markets(), self.grvt.load_markets())
        
        self.sizer = TradeSizer(self.hl, self.grvt)
        await self.sizer.initialize()

    async def get_current_price(self, symbol):
        try:
            mids = self.hl.info.all_mids()
            return float(mids.get(symbol, 0))
        except: return 0.0

    # ---------------------------------------------------------
    # 🧹 강제 청산 (초기화용)
    # ---------------------------------------------------------
    async def close_all_existing_positions(self):
        """현재 열려있는 모든 포지션을 조회하여 강제 시장가 청산"""
        log.info("🧹 [초기화] 기존 잔여 포지션 전량 정리 중...")
        tasks = []

        # 1. HL 포지션 조회 및 청산
        try:
            hl_state = self.hl.info.user_state(self.hl.account_address)
            for p in hl_state['assetPositions']:
                coin = p['position']['coin']
                size = float(p['position']['szi'])
                if size != 0:
                    side = "SELL" if size > 0 else "BUY"
                    log.info(f"   Detected HL {coin} {size} -> Closing ({side})...")
                    tasks.append(self.hl.place_market_order(coin, side, abs(size)))
        except Exception as e:
            log.warning(f"⚠️ HL 포지션 조회 실패: {e}")

        # 2. GRVT 포지션 조회 및 청산
        try:
            if self.grvt and self.grvt.grvt:
                grvt_positions = await self.grvt.grvt.fetch_positions()
                for p in grvt_positions:
                    size = float(p.get('size') or p.get('contracts') or 0)
                    if size != 0:
                        sym = p.get('instrument', '') # BTC_USDT_Perp
                        side = "sell" if size > 0 else "buy"
                        log.info(f"   Detected GRVT {sym} {size} -> Closing ({side})...")
                        # GRVT SDK 직접 호출 (place_market_order는 심볼 변환 로직이 있어 직접 호출이 안전)
                        tasks.append(self.grvt.grvt.create_order(
                            symbol=sym, order_type='market', side=side, amount=abs(size)
                        ))
        except Exception as e:
            log.warning(f"⚠️ GRVT 포지션 조회 실패: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            log.info("   ✨ 청소 완료. 5초 대기...")
            await asyncio.sleep(5)
        else:
            log.info("   ✨ 정리할 포지션 없음.")

    # ---------------------------------------------------------
    # 📊 상태 모니터링
    # ---------------------------------------------------------
    async def log_status(self):
        try:
            # HL
            hl_st = self.hl.info.user_state(self.hl.account_address)
            hl_eq = float(hl_st['marginSummary']['accountValue'])
            hl_pos = [f"{p['position']['coin']}:{p['position']['szi']}" for p in hl_st['assetPositions'] if float(p['position']['szi'])!=0]
            
            # GRVT
            grvt_bal = await self.grvt.grvt.fetch_balance()
            grvt_eq = float(grvt_bal.get('USDT', {}).get('total', 0))
            grvt_raw = await self.grvt.grvt.fetch_positions()
            grvt_pos = [f"{p.get('instrument','').split('_')[0]}:{p.get('size')}" for p in grvt_raw if float(p.get('size',0))!=0]

            log.info(f"💰 [잔고] HL ${hl_eq:.1f} ({hl_pos}) | GRVT ${grvt_eq:.1f} ({grvt_pos})")
        except: pass

    def get_synchronized_qty(self, symbol, price, target_notional):
        # 1. 목표 수량 계산 (예: $100 / $3000 = 0.03333)
        raw_qty = target_notional / price
        
        # 2. 거래소별 제약 사항 가져오기
        hl_stats = self.market_map.get(symbol, {}).get('hl', {'min_size': 0.001})
        grvt_stats = self.market_map.get(symbol, {}).get('grvt', {'min_size': 0.01}) # ETH는 0.01

        # 3. [핵심] 두 거래소 중 '더 큰 최소 수량'을 기준으로 잡음
        # ETH의 경우 0.01(GRVT)이 0.001(HL)보다 크므로 0.01이 기준이 됨
        min_executable_size = max(hl_stats['min_size'], grvt_stats['min_size'])
        
        # 4. 기준 수량의 배수로 내림 처리 (0.0333 -> 0.03)
        # 이렇게 해야 양쪽 거래소 모두에서 '잔액 부족'이나 '수량 미달' 에러가 안 납니다.
        synchronized_qty = (raw_qty // min_executable_size) * min_executable_size
        
        return float(Decimal(str(synchronized_qty)).quantize(Decimal(str(min_executable_size)), rounding=ROUND_DOWN))

    # ---------------------------------------------------------
    # ⚔️ 매매 사이클
    # ---------------------------------------------------------
    async def run_cycle(self, round_num):
        entry_tasks = []
        cleanup_map = [] # 실패 시 취소용

        # --- 방향 결정 (홀수/짝수 라운드) ---
        # 홀수: HL [BTC롱, ETH숏] vs GRVT [BTC숏, ETH롱]
        # 짝수: HL [BTC숏, ETH롱] vs GRVT [BTC롱, ETH숏]
        is_odd = (round_num % 2 != 0)
        
        # BTC 방향
        btc_hl_side = "BUY" if is_odd else "SELL"
        btc_grvt_side = "SELL" if is_odd else "BUY"
        
        # ETH 방향 (BTC와 반대)
        eth_hl_side = "SELL" if is_odd else "BUY"
        eth_grvt_side = "BUY" if is_odd else "SELL"

        log.info(f"⚖️ [Round {round_num}] 방향 설정 (Odd={is_odd})")
        log.info(f"   BTC: HL({btc_hl_side}) vs GRVT({btc_grvt_side})")
        log.info(f"   ETH: HL({eth_hl_side}) vs GRVT({eth_grvt_side})")

        # --- 주문 생성 ---
        for symbol in SYMBOLS:
            price = await self.get_current_price(symbol)
            if price <= 0: continue
            
            # [수정] sizer를 통해 정밀도가 보정된 수량을 가져옵니다.
            target_size_usd = MARGIN_PER_ASSET * LEVERAGE
            entry_info = self.sizer.calculate_entry_params(symbol, price, target_size_usd)
            
            if not entry_info or entry_info['qty'] <= 0:
                log.warning(f"⚠️ {symbol} 주문 가능 수량 부족 (최소주문량 미달)")
                continue

            amount = entry_info['qty']
            log.info(f"💎 {symbol} 동기화 수량 적용: {amount} (약 ${entry_info['notional']:.1f})")
            
            if symbol == "BTC":
                h_side, g_side = btc_hl_side, btc_grvt_side
            else:
                h_side, g_side = eth_hl_side, eth_grvt_side

            # 주문 Task
            entry_tasks.append(self.hl.place_market_order(symbol, h_side, amount))
            entry_tasks.append(self.grvt.place_market_order(symbol, g_side, amount))
            
            # 청산용 매핑 (성공했다 치고 저장)
            cleanup_map.append({'sym': symbol, 'ex': 'HL', 'side': h_side, 'amt': amount})
            cleanup_map.append({'sym': symbol, 'ex': 'GRVT', 'side': g_side, 'amt': amount})

        # --- 진입 실행 ---
        log.info("🚀 주문 동시 전송...")
        results = await asyncio.gather(*entry_tasks, return_exceptions=True)
        
        success_count = 0
        active_positions = [] # 나중에 청산할 리스트

        for i, res in enumerate(results):
            meta = cleanup_map[i]
            if res is None or isinstance(res, Exception):
                log.error(f"   ❌ 실패: {meta['ex']} {meta['sym']} {meta['side']}")
            else:
                success_count += 1
                active_positions.append(meta)

        if success_count < 4:
            log.warning("⚠️ 일부 주문 실패! 즉시 청산합니다.")
            await asyncio.sleep(1)
            # 실패 시 잡힌 것만이라도 바로 청산 (active_positions 이용)
        else:
            # 성공 시 대기
            hold_time = random.randint(MIN_HOLD_SEC, MAX_HOLD_SEC)
            log.info(f"✅ 4/4 진입 완료. {hold_time}초간 파밍(유지)...")
            await self.log_status()
            await asyncio.sleep(hold_time)

        # --- 청산 실행 (Active Positions 역주문) ---
        log.info("🧹 라운드 종료 및 청산...")
        exit_tasks = []
        for pos in active_positions:
            close_side = "SELL" if pos['side'] == "BUY" else "BUY"
            if pos['ex'] == 'HL':
                exit_tasks.append(self.hl.place_market_order(pos['sym'], close_side, pos['amt']))
            else:
                exit_tasks.append(self.grvt.place_market_order(pos['sym'], close_side, pos['amt']))
        
        await asyncio.gather(*exit_tasks, return_exceptions=True)
        log.info("🏁 청산 완료")

    async def run(self):
        await self.initialize()
        
        round_count = 1
        while True:
            try:
                log.info(f"\n🔄 === Round {round_count} 시작 ===")
                
                # [수정] self.hl.close_all_positions() 대신 아래 함수를 사용해야 합니다.
                # 이 함수는 VolumeFarmer 클래스 내부에 정의된 '전체 청산' 로직입니다.
                await self.close_all_existing_positions()
                
                # 2. 매매 사이클 실행
                await self.run_cycle(round_count)
                
                # 3. 휴식
                rest = random.randint(MIN_REST_SEC, MAX_REST_SEC)
                log.info(f"💤 {rest}초 휴식...")
                await asyncio.sleep(rest)
                
                round_count += 1

            except KeyboardInterrupt:
                log.info("정지 요청 감지. 프로그램을 종료합니다.")
                break
            except Exception as e:
                log.error(f"Bot Error: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    farmer = VolumeFarmer()
    asyncio.run(farmer.run())