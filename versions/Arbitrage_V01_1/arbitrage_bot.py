import asyncio
import sys
import os
import logging 
import traceback
import time
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path): load_dotenv(dotenv_path=dotenv_path)
except ImportError: pass

try:
    import settings
    from portfolio_manager import PortfolioManager
    from virtual_portfolio_manager import VirtualPortfolioManager
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange, 
        ExtendedExchange, LighterExchange
    )
except ImportError as e:
    print(f"❌ 모듈 임포트 실패: {e}")
    sys.exit(1)

log = logging.getLogger("ArbitrageBot") 
if not log.hasHandlers():
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log.addHandler(handler)

class ArbitrageBot:
    def __init__(self, loop):
        self.loop = loop
        self.is_running = False
        
        # 1. 거래소 초기화
        self.exchanges = {
            'hyperliquid': HyperliquidExchange(os.getenv("HL_PRIVATE_KEY"), os.getenv("HL_ACCOUNT_ADDRESS")),
            'grvt': GrvtExchange(os.getenv("GRVT_API_KEY"), os.getenv("GRVT_SECRET_KEY"), os.getenv("GRVT_TRADING_ACCOUNT_ID")),
            'pacifica': PacificaExchange(os.getenv("PACIFICA_PRIVATE_KEY"), os.getenv("PACIFICA_ADDRESS")),
            'extended': ExtendedExchange(os.getenv("EXTENDED_PRIVATE_KEY"), os.getenv("EXTENDED_ADDRESS")),
            'lighter': LighterExchange(os.getenv("LIGHTER_API_KEY"), os.getenv("LIGHTER_PUBLIC_KEY"))
        }

        # 2. 포트폴리오 매니저
        self.recorder = PortfolioManager()
        self.virtual_portfolio = VirtualPortfolioManager(
            balances=settings.SIMULATION_CONFIG['INITIAL_BALANCES'],
            fees=settings.SIMULATION_CONFIG['FEES'],
            portfolio_recorder=self.recorder
        )

        # 3. 데이터 저장소 (GUI 공유용)
        self.live_market_data = {} 
        self._init_market_data()

        self.tasks = []

    def _init_market_data(self):
        """모든 타겟 코인을 초기화 (화면에 바로 뜨게 함)"""
        for ticker in settings.TARGET_PAIRS_CONFIG.keys():
            self.live_market_data[ticker] = {
                'spread': 0.0,
                'long_ex': 'Connecting...',
                'short_ex': 'Connecting...',
                'timestamp': time.time()
            }

    async def start(self):
        log.info("🚀 5대 거래소 봇 가동 (비동기 아키텍처 V2)")
        self.is_running = True
        
        # 1. 웹소켓 연결 (병렬)
        await self._connect_and_subscribe()
        
        # 2. 백그라운드 작업 시작 (스캐너, 포지션 감시, 엑셀 저장)
        self.tasks.append(asyncio.create_task(self._market_scanner_loop()))   # [핵심] 0.5초마다 계산
        self.tasks.append(asyncio.create_task(self._position_monitor_loop())) # 1초마다 청산 확인
        self.tasks.append(asyncio.create_task(self._periodic_save_loop()))    # 10초마다 저장

        # 메인 루프 유지
        while self.is_running:
            await asyncio.sleep(1)

    async def stop(self):
        log.info("🛑 봇 종료 요청...")
        self.is_running = False
        for task in self.tasks: task.cancel()
        for ex in self.exchanges.values(): await ex.close()
        log.info("✅ 종료 완료")

    async def _connect_and_subscribe(self):
        """모든 거래소 웹소켓 연결"""
        tasks = []
        for exchange in self.exchanges.values():
            # 콜백은 단순히 캐시만 업데이트 (매우 빠름)
            tasks.append(exchange.start_ws(self._on_market_update))
        
        for t in tasks: asyncio.create_task(t)
        await asyncio.sleep(2) # 초기 연결 대기
        log.info("✅ 데이터 수신 파이프라인 가동")

    async def _on_market_update(self, bbo_data: Dict):
        """
        [최적화] 여기서는 계산을 하지 않습니다!
        데이터가 들어오면 각 Exchange 객체 내부의 bbo_cache에 이미 저장되었으므로
        여기서는 아무것도 안 하거나, 간단한 로깅만 합니다.
        """
        pass 

    # ==================================================================
    # 🧠 [핵심] 주기적 스캐너 (Data -> Decision)
    # ==================================================================
    async def _market_scanner_loop(self):
        log.info("🧠 마켓 스캐너 엔진 시동")
        while self.is_running:
            start_time = time.time()
            
            for ticker in list(settings.TARGET_PAIRS_CONFIG.keys()):
                await self._process_ticker(ticker)
                
            # [수정 추가] 포지션 미실현 PnL 계산 (GUI 업데이트를 위해)
            await self._update_unrealized_pnl()
            
            elapsed = time.time() - start_time
            sleep_time = max(0.1, 0.5 - elapsed)
            await asyncio.sleep(sleep_time)

    async def _update_unrealized_pnl(self):
        """[신규] 모든 활성 포지션의 미실현 PnL을 계산하여 저장"""
        for ex_name, positions in self.virtual_portfolio.positions.items():
            for ticker, pos_data in positions.items():
                curr_bbo = self.exchanges[ex_name].get_bbo(ticker)
                if not curr_bbo: continue
                
                entry_price = pos_data['price']
                qty = pos_data['qty']
                
                # 매수(롱) 포지션: (현재 매도가 - 진입가) * 수량
                if pos_data['side'] in ['BUY', 'LONG']:
                    current_exit_price = float(curr_bbo['bid'])
                    pnl = (current_exit_price - entry_price) * qty
                
                # 매도(숏) 포지션: (진입가 - 현재 매수가) * 수량
                elif pos_data['side'] in ['SELL', 'SHORT']:
                    current_exit_price = float(curr_bbo['ask'])
                    pnl = (entry_price - current_exit_price) * qty
                
                # PnL 업데이트
                self.virtual_portfolio.positions[ex_name][ticker]['pnl'] = pnl
                
                # [GUI용] 포지션 창의 PnL 정보 업데이트 (PnL에 Active 대신 PnL이 뜨도록)
                # 이 값은 GUI_DASHBOARD에서 읽어갑니다.
                self.live_market_data[ticker]['active_pnl'] = pnl

    async def _periodic_save_loop(self):
        while self.is_running:
            await asyncio.sleep(10)
            if self.recorder:
                try: 
                    # [수정] log.txt 에러 확인
                    # portfolio_manager.py의 log_trade에서 trade_type을 넘겼으므로, 
                    # export_trade_log_to_excel의 인자를 제거하여 기본값으로 호출합니다.
                    self.recorder.export_trade_log_to_excel()
                except Exception as e:
                    # [문제3 해결] 엑셀 저장 오류가 나면 명확하게 로그 출력
                    log.error(f"❌ 엑셀 저장 중 오류: {e}")
                    
    async def _process_ticker(self, ticker: str):
        """개별 코인의 최적 스프레드 계산"""
        quotes = []
        current_time = time.time()
        VALID_WINDOW = 30.0 # 데이터 유효 시간

        # 1. 5개 거래소 캐시 조회
        for ex_name, exchange in self.exchanges.items():
            bbo = exchange.get_bbo(ticker)
            if bbo:
                # 유효성 검사 (시간, 가격)
                data_time = bbo.get('timestamp', 0)
                price_bid = float(bbo.get('bid', 0))
                price_ask = float(bbo.get('ask', 0))
                
                if price_bid > 0 and price_ask > 0:
                    if current_time - data_time < VALID_WINDOW:
                        quotes.append({
                            'ex': ex_name,
                            'bid': price_bid,
                            'ask': price_ask
                        })

        # 2. GUI 데이터 업데이트 준비
        status_data = {
            'spread': 0.0,
            'long_ex': 'Waiting',
            'short_ex': 'Waiting',
            'timestamp': current_time
        }

        # 하나라도 있으면 표시
        if len(quotes) == 1:
            status_data['long_ex'] = f"{quotes[0]['ex']} Only"
            status_data['short_ex'] = f"${quotes[0]['ask']:.4f}"

        # 3. 2개 이상이면 스프레드 계산 & 진입 판단
        if len(quotes) >= 2:
            sorted_asks = sorted(quotes, key=lambda x: x['ask']) # 롱 (싼 곳)
            sorted_bids = sorted(quotes, key=lambda x: x['bid'], reverse=True) # 숏 (비싼 곳)
            
            best_long = sorted_asks[0]
            best_short = sorted_bids[0]

            if best_long['ex'] != best_short['ex']:
                spread_pct = (best_short['bid'] - best_long['ask']) / best_long['ask'] * 100
                
                status_data = {
                    'spread': spread_pct,
                    'long_ex': best_long['ex'],
                    'short_ex': best_short['ex'],
                    'timestamp': current_time
                }
                
                # 진입 로직 실행
                await self._check_entry(ticker, best_long, best_short, spread_pct)

        # GUI 공유 변수 갱신 (Thread-safe하게)
        self.live_market_data[ticker] = status_data

    async def _check_entry(self, ticker, long_data, short_data, spread):
        """진입 조건 검사"""
        # 1. 데이터 오류 필터 (10% 이상은 무시)
        if spread > 10.0: return

        # 2. 설정값 확인
        target_cfg = settings.TARGET_PAIRS_CONFIG[ticker]
        preset_name = target_cfg.get('strategy_preset', 'volatile')
        threshold = settings.STRATEGY_PRESETS[preset_name]['entry_threshold_pct']

        # 3. 이미 보유 중인지 확인 (중복 진입 차단)
        for ex_name in self.exchanges:
            if self.virtual_portfolio.get_position(ex_name, ticker): 
                # log.info(f"❌ [진입 중단] {ticker}: 포지션 보유 중 (무시)") # 로그 도배 방지용 주석 처리
                return

        # 4. 진입 실행
        if spread >= threshold:
            await self._execute_entry(ticker, long_data, short_data, spread)
            size_usd = target_cfg.get('trade_size_fixed_usd', 20.0)
            qty = size_usd / long_data['ask']
            
            # 잔고 확인
            if self.virtual_portfolio.can_afford(long_data['ex'], long_data['ask'], qty) and \
               self.virtual_portfolio.can_afford(short_data['ex'], short_data['bid'], qty):
                
                log.info(f"🚀 [진입] {ticker}: {long_data['ex']}->{short_data['ex']} ({spread:.2f}%)")
                self.virtual_portfolio.add_trade(long_data['ex'], ticker, 'BUY', long_data['ask'], qty, 'ENTRY')
                self.virtual_portfolio.add_trade(short_data['ex'], ticker, 'SELL', short_data['bid'], qty, 'ENTRY')
    
    async def _execute_entry(self, ticker, long_data, short_data, spread):
        try:
            target_cfg = settings.TARGET_PAIRS_CONFIG[ticker]
            size_usd = target_cfg.get('trade_size_fixed_usd', 20.0)
            
            qty = size_usd / long_data['ask']
            
            can_buy = self.virtual_portfolio.can_afford(long_data['ex'], long_data['ask'], qty)
            can_sell = self.virtual_portfolio.can_afford(short_data['ex'], short_data['bid'], qty)
            
            # [문제 해결] 잔고 부족 시 명확한 로그 출력
            if not can_buy or not can_sell:
                log.error(f"❌ [자금 부족] {ticker} 진입 불가. (HL:{long_data['ex']} CanAfford: {can_buy}, GRVT:{short_data['ex']} CanAfford: {can_sell})")
                return

            log.info(f"🚀 [진입] {ticker}: {long_data['ex']}->{short_data['ex']} | 차익: {spread:.2f}%")
            
            self.virtual_portfolio.add_trade(long_data['ex'], ticker, 'BUY', long_data['ask'], qty, 'ENTRY')
            self.virtual_portfolio.add_trade(short_data['ex'], ticker, 'SELL', short_data['bid'], qty, 'ENTRY')
            
        except Exception as e:
            log.error(f"❌ 진입 중 치명적 에러: {e}")

    # ==================================================================
    # 📉 [핵심] 포지션 감시 (Exit)
    # ==================================================================
    async def _position_monitor_loop(self):
        """1초마다 보유 포지션의 손익을 계산하고 청산합니다."""
        while self.is_running:
            try:
                # 모든 보유 포지션 순회
                # (구현 편의상 settings의 ticker 목록을 기준으로 검사)
                for ticker in settings.TARGET_PAIRS_CONFIG.keys():
                    await self._check_exit(ticker)
            except Exception: pass
            await asyncio.sleep(1)

    async def _check_exit(self, ticker):
        active_positions = []
        for ex_name in self.exchanges:
            pos = self.virtual_portfolio.get_position(ex_name, ticker)
            if pos: active_positions.append({'ex': ex_name, 'data': pos})
        
        if len(active_positions) < 2: return

        long_pos = next((p for p in active_positions if p['data']['side'] in ['BUY', 'LONG']), None)
        short_pos = next((p for p in active_positions if p['data']['side'] in ['SELL', 'SHORT']), None)
        
        if not long_pos or not short_pos: return

        # 1. 최소 보유 시간 (60초) 체크
        if time.time() - long_pos['data']['entry_time'] < settings.POSITION_MIN_HOLD_SECONDS:
            return 

        # 2. 현재가 조회
        curr_long = self.exchanges[long_pos['ex']].get_bbo(ticker)
        curr_short = self.exchanges[short_pos['ex']].get_bbo(ticker)
        
        if not curr_long or not curr_short: return # 데이터 없으면 대기

        exit_bid = float(curr_long['bid'])
        exit_ask = float(curr_short['ask'])

        # 3. PnL 계산
        pnl_long = (exit_bid - float(long_pos['data']['price'])) * float(long_pos['data']['qty'])
        pnl_short = (float(short_pos['data']['price']) - exit_ask) * float(short_pos['data']['qty'])
        total_pnl = pnl_long + pnl_short
        
        entry_val = float(long_pos['data']['price']) * float(long_pos['data']['qty'])
        roi_pct = (total_pnl / entry_val) * 100 if entry_val > 0 else 0

        # 4. 청산 판단
        target_cfg = settings.TARGET_PAIRS_CONFIG[ticker]
        preset = settings.STRATEGY_PRESETS[target_cfg.get('strategy_preset', 'volatile')]
        
        # 익절 or 손절 or 타임컷
        should_exit = False
        reason = ""
        
        if roi_pct >= 0.5: # 목표 수익률 (설정값으로 대체 가능)
            should_exit = True; reason = "익절"
        elif roi_pct <= preset['exit_threshold_pct']:
            should_exit = True; reason = "손절"
        elif time.time() - long_pos['data']['entry_time'] > settings.POSITION_MAX_HOLD_SECONDS:
            should_exit = True; reason = "타임컷"

        if should_exit:
            log.info(f"📉 [{reason}] {ticker}: ${total_pnl:.4f} ({roi_pct:.2f}%)")
            self.virtual_portfolio.add_trade(long_pos['ex'], ticker, 'SELL', exit_bid, long_pos['data']['qty'], 'EXIT', pnl=total_pnl/2)
            self.virtual_portfolio.add_trade(short_pos['ex'], ticker, 'BUY', exit_ask, short_pos['data']['qty'], 'EXIT', pnl=total_pnl/2)

    async def _periodic_save_loop(self):
        while self.is_running:
            await asyncio.sleep(10)
            if self.recorder:
                try: self.recorder.export_trade_log_to_excel(0, 0)
                except: pass