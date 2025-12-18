import asyncio
import sys
import os
import logging
import time
from typing import Dict, List, Any, Optional
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
    import settings
    from portfolio_manager import PortfolioManager
    from virtual_portfolio_manager import VirtualPortfolioManager
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange,
        ExtendedExchange, LighterExchange
    )
    from utils.trade_sizer import TradeSizer
except ImportError as e:
    print(f"❌ 필수 모듈 로드 실패: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("arbitrage_bot.log", encoding='utf-8')
    ]
)
# 로그 레벨 조정
for lib in ["pysdk", "GrvtCcxtWS", "websockets", "urllib3", "asyncio"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

log = logging.getLogger("ArbitrageBot")

class ArbitrageBot:
    def __init__(self, loop=None):
        self.loop = loop if loop else asyncio.get_event_loop()
        self.is_running = False
        self.start_time = 0 

        # 1. 설정
        self.active_exchanges = getattr(settings, 'ACTIVE_EXCHANGES', ['hyperliquid', 'grvt'])
        self.real_trading = getattr(settings, 'REAL_TRADING', False)
        
        # 2. 상태 변수
        self.cooldowns = {}
        self.opp_counters = defaultdict(int)
        self.REQUIRED_CONFIRMATIONS = 3
        
        # [자산 관리]
        self.initial_equity = 0.0
        self.current_equity = 0.0
        self.total_pnl = 0.0
        
        # [신규] 거래소별 잔고 관리
        self.exchange_balances = {}       # { 'hyperliquid': 100.0, 'grvt': 50.0 }
        self.initial_exchange_balances = {} # PnL 계산용 초기값

        # 3. 거래소 초기화
        self.exchanges = {}
        self._init_exchanges()

        # 4. 매니저
        self.sizer = TradeSizer(
            self.exchanges.get('hyperliquid'), 
            self.exchanges.get('grvt')
        )
        self.recorder = PortfolioManager() 
        self.virtual_portfolio = VirtualPortfolioManager(
            settings.SIMULATION_CONFIG.get('INITIAL_BALANCES', {}),
            settings.SIMULATION_CONFIG.get('FEES', {}),
            self.recorder
        )
        
        self.market_cache = defaultdict(dict)
        self.cache_lock = asyncio.Lock()
        
        self.real_positions = {} 
        self.max_concurrent_positions = 5

    def _init_exchanges(self):
        if 'hyperliquid' in self.active_exchanges:
            self.exchanges['hyperliquid'] = HyperliquidExchange(
                os.getenv("HYPERLIQUID_PRIVATE_KEY"), 
                os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS")
            )
        if 'grvt' in self.active_exchanges:
            self.exchanges['grvt'] = GrvtExchange(
                os.getenv("GRVT_API_KEY"), 
                os.getenv("GRVT_PRIVATE_KEY") or os.getenv("GRVT_SECRET_KEY"), 
                os.getenv("GRVT_TRADING_ACCOUNT_ID")
            )
        # Dummy exchanges for feed
        for ex in ['pacifica', 'extended', 'lighter']:
            if ex not in self.exchanges: self.exchanges[ex] = PacificaExchange("dummy") # Use dummy class

    async def start(self):
        if self.is_running: return
        self.is_running = True
        self.start_time = time.time()
        
        log.info(f"🚀 봇 가동 (Real Trading: {self.real_trading})")
        
        # 1. 연결
        tasks = []
        if 'grvt' in self.exchanges: tasks.append(self.exchanges['grvt'].connect())
        await asyncio.gather(*tasks)
        
        # 2. 초기 자산 조회 (기준점 설정)
        if self.real_trading:
            await self._update_equity()
            self.initial_equity = self.current_equity
            self.initial_exchange_balances = self.exchange_balances.copy() # 복사 저장
            log.info(f"💰 초기 자산: ${self.initial_equity:,.2f} {self.initial_exchange_balances}")
            
            log.info("⚙️ TradeSizer 초기화...")
            await self.sizer.initialize()

        # 3. 웹소켓 및 루프 시작
        ws_tasks = [ex.start_ws(self._on_market_data) for ex in self.exchanges.values()]
        for t in ws_tasks: self.loop.create_task(t)
        self.loop.create_task(self._monitor_market_loop())

    async def stop(self):
        self.is_running = False
        for ex in self.exchanges.values(): await ex.close()
        log.info("🛑 봇 종료")

    async def _on_market_data(self, data: Dict):
        ticker, ex = data.get('symbol'), data.get('exchange')
        if not ticker or not ex: return
        async with self.cache_lock:
            self.market_cache[ticker][ex] = {
                'bid': float(data['bid']), 'ask': float(data['ask']), 'timestamp': float(data['timestamp'])
            }

    async def _monitor_market_loop(self):
        WARMUP = 5
        log.info(f"⏳ 예열 {WARMUP}초...")
        while self.is_running:
            if time.time() - self.start_time < WARMUP:
                await asyncio.sleep(1); continue
            
            try:
                await self._execute_strategy_logic()
                
                # [중요] 주기적 자산 갱신 (10초마다)
                if self.real_trading and int(time.time()) % 10 == 0:
                    await self._update_equity()

            except Exception as e:
                log.error(f"루프 에러: {e}")
            await asyncio.sleep(0.1)

    async def _execute_strategy_logic(self):
        current_time = time.time()
        async with self.cache_lock: snapshot = self.market_cache.copy()

        # 1. 청산 체크
        active_tickers = list(self.real_positions.keys()) if self.real_trading else self.virtual_portfolio.get_active_tickers()
        for ticker in active_tickers:
            await self._check_exit_condition(ticker, snapshot.get(ticker, {}), current_time)

        # 2. 진입 체크
        if len(active_tickers) >= self.max_concurrent_positions: return
        
        target_coins = list(settings.TARGET_PAIRS_CONFIG.keys())
        for ticker in target_coins:
            if ticker in active_tickers: continue
            if ticker not in snapshot: continue
            if current_time < self.cooldowns.get(ticker, 0): continue

            # 데이터 필터링
            valid = {ex: d for ex, d in snapshot[ticker].items() if current_time - d['timestamp'] < 2.0}
            if len(valid) < 2: 
                self.opp_counters[ticker] = 0; continue

            # 가격 비교
            buy_ex = min(valid, key=lambda x: valid[x]['ask'])
            sell_ex = max(valid, key=lambda x: valid[x]['bid'])
            buy_price = valid[buy_ex]['ask']
            sell_price = valid[sell_ex]['bid']

            if buy_price >= sell_price: 
                self.opp_counters[ticker] = 0; continue

            spread = (sell_price - buy_price) / buy_price * 100
            
            if self.real_trading:
                if buy_ex not in self.active_exchanges or sell_ex not in self.active_exchanges: continue

            cfg = settings.TARGET_PAIRS_CONFIG[ticker]
            preset_name = cfg.get('strategy_preset', 'normal')
            min_spread = settings.STRATEGY_PRESETS.get(preset_name, {}).get('ENTRY_SPREAD', 0.005) * 100

            if spread > min_spread:
                self.opp_counters[ticker] += 1
                if self.opp_counters[ticker] >= self.REQUIRED_CONFIRMATIONS:
                    log.info(f"⚡ [기회] {ticker} Spread:{spread:.2f}% | {buy_ex} -> {sell_ex}")
                    margin = cfg.get('trade_size_fixed_usd', 15.0)
                    
                    if self.real_trading:
                        await self._execute_real_dual_leg(ticker, buy_ex, buy_price, sell_ex, sell_price, margin)
                    else:
                        await self._execute_virtual_dual_leg(ticker, buy_ex, buy_price, sell_ex, sell_price, margin, spread)
                    
                    self.opp_counters[ticker] = 0
                    self.cooldowns[ticker] = current_time + self.COOLDOWN_SECONDS
            else:
                self.opp_counters[ticker] = 0

    async def _execute_real_dual_leg(self, ticker, buy_ex, buy_price, sell_ex, sell_price, margin_usd):
        plan = self.sizer.calculate_entry_params(ticker, buy_price, margin_usd)
        if not plan:
            log.warning(f"⛔ {ticker} 진입 불가 (조건 미달)")
            return
        
        qty = plan['qty']
        log.info(f"🚀 [실전 진입] {ticker} {qty} (Lev: {plan['leverage']:.1f}x)")
        
        tasks = []
        # Buy
        if buy_ex == 'hyperliquid': tasks.append(self.exchanges['hyperliquid'].create_order(ticker, 'BUY', buy_price*1.05, qty))
        elif buy_ex == 'grvt': tasks.append(self.exchanges['grvt'].create_order(ticker, 'BUY', None, qty))
        # Sell
        if sell_ex == 'hyperliquid': tasks.append(self.exchanges['hyperliquid'].create_order(ticker, 'SELL', sell_price*0.95, qty))
        elif sell_ex == 'grvt': tasks.append(self.exchanges['grvt'].create_order(ticker, 'SELL', None, qty))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 검증
        log.info("🔍 포지션 검증 중...")
        await asyncio.sleep(2)
        chk_buy = await self.verify_position(buy_ex, ticker, qty)
        chk_sell = await self.verify_position(sell_ex, ticker, qty)

        if chk_buy and chk_sell:
            log.info(f"✅ {ticker} 양방향 진입 성공")
            self.real_positions[ticker] = {
                'entry_time': time.time(), 'qty': qty,
                'long_ex': buy_ex, 'short_ex': sell_ex, 'entry_price': buy_price
            }
            # 자산 즉시 갱신
            await self._update_equity()
        else:
            log.error(f"❌ {ticker} 진입 실패 (Rollback 필요)")
            await self.execute_real_exit(ticker, {'long_ex': buy_ex, 'short_ex': sell_ex, 'qty': qty})

    async def _check_exit_condition(self, ticker, market_data, current_time):
        if self.real_trading:
            pos = self.real_positions.get(ticker)
        else:
            v_pos = self.virtual_portfolio.get_active_position(ticker)
            pos = {'entry_time': v_pos['long']['data']['entry_time'], 'long_ex': v_pos['long']['ex'], 'short_ex': v_pos['short']['ex'], 'qty': v_pos['long']['data']['qty']} if v_pos else None

        if not pos or pos['long_ex'] not in market_data or pos['short_ex'] not in market_data: return

        bid = market_data[pos['long_ex']]['bid']
        ask = market_data[pos['short_ex']]['ask']
        spread = (ask - bid) / bid * 100
        
        cfg = settings.TARGET_PAIRS_CONFIG[ticker]
        preset = settings.STRATEGY_PRESETS.get(cfg.get('strategy_preset', 'normal'), {})
        target = preset.get('EXIT_SPREAD', 0.001) * 100

        if spread <= target:
            log.info(f"💰 [익절] {ticker} Spread:{spread:.2f}%")
            if self.real_trading: await self.execute_real_exit(ticker, pos)
            else: self._execute_virtual_exit(ticker, pos, bid, ask)
        elif current_time - pos['entry_time'] > 7200:
            log.info(f"⏰ [타임컷] {ticker}")
            if self.real_trading: await self.execute_real_exit(ticker, pos)
            else: self._execute_virtual_exit(ticker, pos, bid, ask)

    async def execute_real_exit(self, ticker, pos):
        log.info(f"🚨 {ticker} 청산 시작...")
        tasks = [
            self.exchanges[pos['long_ex']].close_position(ticker),
            self.exchanges[pos['short_ex']].close_position(ticker)
        ]
        await asyncio.gather(*tasks)
        log.info(f"✅ {ticker} 청산 완료")
        if ticker in self.real_positions: del self.real_positions[ticker]
        self.cooldowns[ticker] = time.time() + 60
        await self._update_equity()

    async def _update_equity(self):
        """[핵심] 실제 거래소 잔고 조회 및 갱신"""
        total = 0.0
        for name, ex in self.exchanges.items():
            if name in ['hyperliquid', 'grvt']:
                bal = await ex.get_balance()
                if bal:
                    eq = bal.get('equity', 0.0)
                    self.exchange_balances[name] = eq # 개별 잔고 저장
                    total += eq
        
        self.current_equity = total
        if self.initial_equity > 0:
            self.total_pnl = self.current_equity - self.initial_equity

    async def verify_position(self, ex_name, ticker, exp_qty):
        try:
            bal = await self.exchanges[ex_name].get_balance()
            actual = 0.0
            for p in bal.get('positions', []):
                # HL
                if 'position' in p and p['position']['coin'] == ticker:
                    actual = float(p['position']['szi'])
                    break
                # GRVT
                if ex_name == 'grvt':
                    sym = p.get('instrument') or p.get('symbol') or ""
                    if ticker in sym: 
                        actual = float(p.get('contracts') or p.get('size') or 0)
                        break
            
            if abs(abs(actual) - abs(exp_qty)) / exp_qty < 0.05: return True
        except: pass
        return False

    # --- 기존 가상 매매 메서드들 (로그용) ---
    async def _execute_virtual_dual_leg(self, ticker, buy_ex, buy_price, sell_ex, sell_price, usd_margin, spread_pct):
        qty = (usd_margin * 5) / buy_price # 가상은 5배 고정
        self.virtual_portfolio.add_trade(buy_ex, ticker, 'BUY', buy_price, qty, 'ENTRY')
        self.virtual_portfolio.add_trade(sell_ex, ticker, 'SELL', sell_price, qty, 'ENTRY')
        log.info(f"🚀 [가상 진입] {ticker} Spread:{spread_pct:.2f}%")

    def _execute_virtual_exit(self, ticker, pos, exit_bid, exit_ask):
        self.virtual_portfolio.add_trade(pos['long_ex'], ticker, 'SELL', exit_bid, pos['qty'], 'EXIT')
        self.virtual_portfolio.add_trade(pos['short_ex'], ticker, 'BUY', exit_ask, pos['qty'], 'EXIT')
        self.cooldowns[ticker] = time.time()

    def save_excel(self):
        self.recorder.export_trade_log_to_excel(balances=self.virtual_portfolio.balances)

if __name__ == "__main__":
    bot = ArbitrageBot()
    asyncio.run(bot.start())