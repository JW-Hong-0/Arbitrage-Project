import asyncio
import sys
import logging
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# 사용자 모듈 로드
from exchange_apis import HyperliquidExchange, GrvtExchange
from utils.trade_sizer import TradeSizer

# 설정 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [BOT] - %(message)s',
    datefmt='%H:%M:%S'
)
# 불필요한 라이브러리 로그 끄기
logging.getLogger("pysdk").setLevel(logging.ERROR)
logging.getLogger("GrvtCcxtWS").setLevel(logging.ERROR)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("ArbitrageBot")

# --- 봇 설정 ---
CONFIG = {
    'TICKER': 'BTC',
    'MARGIN_PER_TRADE': 15.0,   # 거래당 투입 증거금 ($)
    'ENTRY_SPREAD': 0.005,      # 진입 목표 스프레드 (0.5%) - 테스트용으로 낮게 설정 가능
    'EXIT_SPREAD': 0.001,       # 청산 목표 스프레드 (0.1%)
    'POLL_INTERVAL': 0.1,       # 메인 루프 주기 (초)
    'STATUS_INTERVAL': 10,      # 상태 출력 주기 (초)
}

class ArbitrageBot:
    def __init__(self):
        # 1. 거래소 초기화
        self.hl = HyperliquidExchange(
            private_key=os.getenv("HYPERLIQUID_PRIVATE_KEY"),
            main_address=os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS")
        )
        self.grvt = GrvtExchange(
            api_key=os.getenv("GRVT_API_KEY"),
            private_key=os.getenv("GRVT_PRIVATE_KEY") or os.getenv("GRVT_SECRET_KEY"),
            sub_account_id=os.getenv("GRVT_TRADING_ACCOUNT_ID")
        )
        
        # 2. 유틸리티 초기화
        self.sizer = TradeSizer(self.hl, self.grvt)
        
        # 3. 상태 변수
        self.prices = {'HL': 0.0, 'GRVT': 0.0}
        self.in_position = False
        self.position_size = 0.0
        self.entry_spread_val = 0.0
        self.last_status_time = 0
        self.running = False

    async def initialize(self):
        """초기화 및 데이터 동기화"""
        logger.info("🔌 거래소 연결 중...")
        
        # GRVT 연결 (HL은 자동)
        if not await self.grvt.connect():
            logger.error("❌ GRVT 연결 실패. 종료합니다.")
            sys.exit(1)
            
        logger.info("✅ 거래소 연결 완료")

        # 시장 데이터 동기화 (Min Size, Max Lev 등)
        logger.info("⚙️ 시장 데이터 분석 중...")
        await self.sizer.initialize()
        
        # 검증: get_instrument_stats 동작 확인
        ticker = CONFIG['TICKER']
        stats = self.sizer.market_map.get(ticker)
        if stats:
            logger.info(f"🔍 [{ticker} 정보 확인]")
            logger.info(f"   - HL  : Min {stats['hl']['min_size']} | MaxLev {stats['hl']['max_lev']}x")
            logger.info(f"   - GRVT: Min {stats['grvt']['min_size']} | MaxLev {stats['grvt']['max_lev']}x")
        else:
            logger.warning(f"⚠️ {ticker} 정보를 가져오지 못했습니다. 기본값을 사용합니다.")

    async def on_price_update(self, bbo):
        """웹소켓 가격 업데이트 콜백"""
        ex_name = 'HL' if bbo['exchange'] == 'hyperliquid' else 'GRVT'
        mid_price = (bbo['bid'] + bbo['ask']) / 2
        self.prices[ex_name] = mid_price

    async def start_feeds(self):
        """가격 수신 시작"""
        # HL, GRVT 웹소켓 리스너를 비동기 태스크로 실행
        asyncio.create_task(self.hl.start_ws(self.on_price_update))
        # GRVT는 create_order 호출 시 내부적으로 연결되지만, 시세 수신용 별도 로직이 필요할 수 있음
        # exchange_apis.py의 GrvtExchange.start_ws는 구현되어 있지 않으므로(빈 루프), 
        # 여기서는 Ticker/Orderbook 폴링으로 대체하거나 기존 코드의 WS 로직을 살려야 함.
        # *안정성을 위해 여기서는 봇 메인 루프에서 GRVT 가격을 REST/WS로 가져오는 방식을 병행합니다.*

    async def fetch_prices(self):
        """가격 정보 갱신 (WS 보완용)"""
        # GRVT 현재가 가져오기
        try:
            if hasattr(self.grvt.ws, 'fetch_ticker'):
                t = await self.grvt.ws.fetch_ticker(f"{CONFIG['TICKER']}_USDT_Perp")
                p = float(t.get('last') or t.get('last_price'))
                if p > 0: self.prices['GRVT'] = p
        except: pass

        # HL은 WS가 자동으로 self.prices 업데이트 (exchange_apis.py 로직 의존)
        # 만약 HL WS가 느리다면 여기서 REST로 보완 가능

    async def check_opportunity(self):
        """차익거래 기회 포착 및 매매 로직"""
        hl_price = self.prices.get('HL', 0)
        grvt_price = self.prices.get('GRVT', 0)

        if hl_price == 0 or grvt_price == 0:
            return

        # 스프레드 계산 (GRVT가 더 비쌀 때: HL Long / GRVT Short)
        # Spread = (비싼곳 - 싼곳) / 싼곳
        if grvt_price > hl_price:
            spread = (grvt_price - hl_price) / hl_price
            direction = "HL_LONG_GRVT_SHORT"
        else:
            spread = (hl_price - grvt_price) / grvt_price
            direction = "GRVT_LONG_HL_SHORT" # (현재 구현은 HL Long만 가정하지만 확장 가능)

        # 1. 진입 로직 (포지션 없을 때)
        if not self.in_position:
            # 목표: HL에서 싸게 사서 GRVT에서 비싸게 팔기 (HL Long + GRVT Short)
            if direction == "HL_LONG_GRVT_SHORT" and spread >= CONFIG['ENTRY_SPREAD']:
                logger.info(f"✨ 기회 포착! Spread: {spread*100:.3f}% (HL ${hl_price:.1f} / GRVT ${grvt_price:.1f})")
                await self.execute_entry(hl_price, CONFIG['MARGIN_PER_TRADE'])

        # 2. 청산 로직 (포지션 있을 때)
        elif self.in_position:
            # 진입 당시보다 스프레드가 충분히 줄어들었으면 청산
            # 수익 = 진입 스프레드 - 현재 스프레드 - 수수료
            current_spread = spread if direction == "HL_LONG_GRVT_SHORT" else -spread # 방향 고려
            
            # 목표 청산 스프레드 도달 시
            if current_spread <= CONFIG['EXIT_SPREAD']:
                logger.info(f"💰 익절 조건 도달! Spread: {current_spread*100:.3f}% (Entry: {self.entry_spread_val*100:.3f}%)")
                await self.execute_exit()

    async def execute_entry(self, price, margin):
        """진입 실행"""
        logger.info("🚀 진입 시도...")
        
        # TradeSizer로 수량 계산
        plan = self.sizer.calculate_entry_params(CONFIG['TICKER'], price, margin)
        if not plan:
            logger.warning("⛔ 진입 실패: 조건 불충족 (자금/레버리지/최소수량)")
            return

        qty = plan['qty']
        
        # 주문 전송 (HL Long, GRVT Short)
        # HL: Limit IOC (슬리피지 5%)
        task_hl = self.hl.create_order(CONFIG['TICKER'], 'BUY', price * 1.05, qty)
        # GRVT: Market
        task_grvt = self.grvt.create_order(CONFIG['TICKER'], 'SELL', None, qty)

        res_hl, res_grvt = await asyncio.gather(task_hl, task_grvt)

        # 결과 처리
        success_hl = res_hl and res_hl.get('status') == 'ok'
        success_grvt = res_grvt is not None # GRVT는 dict 반환이면 성공으로 간주 (상세 체크 필요)

        if success_hl and success_grvt:
            logger.info(f"✅ 양방향 진입 완료! (Size: {qty} BTC)")
            self.in_position = True
            self.position_size = qty
            self.entry_spread_val = (self.prices['GRVT'] - self.prices['HL']) / self.prices['HL']
        else:
            logger.error("❌ 진입 중 한쪽 실패! (즉시 청산/레깅 처리 필요)")
            # 실제 운영 시에는 여기서 성공한 쪽을 다시 청산하는 'Rollback' 로직이 필요함
            if success_hl: await self.hl.close_position(CONFIG['TICKER'])
            if success_grvt: await self.grvt.close_position(CONFIG['TICKER'])

    async def execute_exit(self):
        """청산 실행"""
        logger.info("🚨 청산 시도...")
        
        task_hl = self.hl.close_position(CONFIG['TICKER'])
        task_grvt = self.grvt.close_position(CONFIG['TICKER'])
        
        await asyncio.gather(task_hl, task_grvt)
        
        logger.info("✅ 청산 완료")
        self.in_position = False
        self.position_size = 0.0

    async def print_status_loop(self):
        """주기적 상태 출력"""
        if time.time() - self.last_status_time > CONFIG['STATUS_INTERVAL']:
            spread = 0
            if self.prices['HL'] > 0:
                spread = (self.prices['GRVT'] - self.prices['HL']) / self.prices['HL'] * 100
            
            status_msg = f"[대기] Spread: {spread:.3f}% | HL: ${self.prices['HL']:.1f} | GRVT: ${self.prices['GRVT']:.1f}"
            if self.in_position:
                status_msg = f"[보유] Size: {self.position_size} BTC | EntrySpread: {self.entry_spread_val*100:.3f}% -> Curr: {spread:.3f}%"
            
            logger.info(status_msg)
            self.last_status_time = time.time()

    async def run(self):
        """메인 루프"""
        await self.initialize()
        await self.start_feeds()
        
        self.running = True
        logger.info("🚀 봇 시작! (Ctrl+C로 중단)")
        
        try:
            while self.running:
                await self.fetch_prices()   # 가격 갱신
                await self.check_opportunity() # 매매 판단
                await self.print_status_loop() # 상태 출력
                await asyncio.sleep(CONFIG['POLL_INTERVAL'])
        except KeyboardInterrupt:
            logger.info("🛑 봇 중단 요청됨")
        except Exception as e:
            logger.error(f"⚠️ 봇 에러 발생: {e}", exc_info=True)
        finally:
            await self.grvt.close()
            await self.hl.close()

if __name__ == "__main__":
    bot = ArbitrageBot()
    asyncio.run(bot.run())