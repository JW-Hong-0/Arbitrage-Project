import asyncio
import logging
import sys
import os
import traceback
import time
import requests
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [BOT] - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("arbitrage_bot_v5.log", encoding='utf-8')
    ]
)
log = logging.getLogger("ArbitrageBot")

try:
    import settings
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange,
        LighterExchange, ExtendedExchange
    )
    from portfolio_manager import PortfolioManager
    from utils.market_sync import MarketSynchronizer
except ImportError as e:
    log.error(f"❌ 필수 모듈 임포트 실패: {e}")
    sys.exit(1)

class ArbitrageBot:
    def __init__(self):
        self.exchanges = {}
        self.pm = None
        self.market_sync = None
        self.is_running = False
        
        self.bbo_cache = {} 
        self.opportunity_cache = {}
        self.active_positions = {} 
        
        self.ex_name_map = {
            'HYPERLIQUID': 'HL', 'GRVT': 'GRVT', 
            'PACIFICA': 'PAC', 'LIGHTER': 'LTR', 'EXTENDED': 'EXT'
        }

    async def initialize(self):
        log.info("==========================================")
        log.info("🚀 [V01_5] Arbitrage Bot 가동 (Time Logic On)")
        log.info("==========================================")
        
        self._init_exchanges()
        if not self.exchanges:
            log.error("❌ 연결된 거래소가 없습니다.")
            sys.exit(1)

        self.market_sync = MarketSynchronizer(self.exchanges)
        await self.market_sync.warm_up()
        
        self.pm = PortfolioManager(self.exchanges, filename="arbitrage_log_real.xlsx")
        await self.pm.update_balances()
        
        log.info("✅ 시스템 초기화 완료.\n")

    def _init_exchanges(self):
        if os.getenv('HYPERLIQUID_PRIVATE_KEY'):
            self.exchanges['HL'] = HyperliquidExchange(os.getenv('HYPERLIQUID_PRIVATE_KEY'))
        if os.getenv('GRVT_API_KEY'):
            self.exchanges['GRVT'] = GrvtExchange()
        if os.getenv('PACIFICA_MAIN_ADDRESS'):
            self.exchanges['PAC'] = PacificaExchange(os.getenv('PACIFICA_MAIN_ADDRESS'), os.getenv('PACIFICA_AGENT_PRIVATE_KEY'))
        if os.getenv('LIGHTER_PRIVATE_KEY'):
            self.exchanges['LTR'] = LighterExchange(os.getenv('LIGHTER_PRIVATE_KEY'), os.getenv('LIGHTER_WALLET_ADDRESS'))
        if os.getenv('EXTENDED_API_KEY'):
            self.exchanges['EXT'] = ExtendedExchange(
                os.getenv('EXTENDED_PRIVATE_KEY'), os.getenv('EXTENDED_PUBLIC_KEY'),
                os.getenv('EXTENDED_API_KEY'), os.getenv('EXTENDED_VAULT')
            )
        log.info(f"🔌 연결된 거래소: {list(self.exchanges.keys())}")

    async def run(self):
        await self.initialize()
        self.is_running = True
        
        ws_tasks = []
        for name, ex in self.exchanges.items():
            ws_tasks.append(asyncio.create_task(ex.start_ws(self.on_price_update)))
            
        log.info("📡 WebSocket 데이터 수신 시작...")
        await self._wait_for_prices()
        
        log.info("⚔️ 차익거래 및 청산 감시 시작!")
        
        try:
            while self.is_running:
                # 1초마다 포지션 모니터링 (청산 기회 포착)
                await self.monitor_active_positions()
                
                # 1초 대기 (CPU 과부하 방지)
                await asyncio.sleep(1)
                
                # 1분마다 잔고 업데이트
                if int(time.time()) % 60 == 0:
                    await self.pm.update_balances()
                
        except Exception as e:
            log.error(f"❌ 봇 런타임 에러: {e}")
            traceback.print_exc()
        finally:
            self.is_running = False
            for t in ws_tasks: t.cancel()
            for ex in self.exchanges.values():
                await ex.close()
            log.info("👋 봇이 안전하게 종료되었습니다.")

    async def _wait_for_prices(self):
        targets = list(settings.TARGET_PAIRS_CONFIG.keys())
        log.info(f"⏳ 가격 데이터 수신 대기 중... (Targets: {len(targets)})")
        
        start = time.time()
        while time.time() - start < 30: 
            ready_count = 0
            for t in targets:
                if t in self.bbo_cache and len(self.bbo_cache[t]) >= 2:
                    ready_count += 1
            if ready_count >= len(targets) * 0.8:
                log.info("✅ 주요 마켓 데이터 수신 완료!")
                return
            await asyncio.sleep(1)
        log.warning("⚠️ 일부 가격 데이터 미수신 상태로 시작합니다.")

    async def on_price_update(self, bbo):
        if not bbo: return
        symbol = bbo['symbol']
        raw_ex = bbo['exchange'].upper()
        exchange = self.ex_name_map.get(raw_ex, raw_ex[:3])
        
        if symbol not in self.bbo_cache: self.bbo_cache[symbol] = {}
        self.bbo_cache[symbol][exchange] = bbo
        
        await self.find_arbitrage_opportunity(symbol)

    async def get_price_robust(self, ex_name, ticker):
        if ticker in self.bbo_cache and ex_name in self.bbo_cache[ticker]:
            bbo = self.bbo_cache[ticker][ex_name]
            return (bbo['bid'] + bbo['ask']) / 2
        ex = self.exchanges.get(ex_name)
        if not ex: return 0.0
        try:
            if ex_name == "GRVT":
                 t = await ex.grvt.fetch_ticker(f"{ticker}_USDT_Perp")
                 return float(t.get('last') or 0)
            elif ex_name == "EXT":
                 res = await asyncio.get_running_loop().run_in_executor(None, lambda: requests.get(f"https://api.starknet.extended.exchange/v1/orderbooks/{ticker}-USD", timeout=2))
                 if res.status_code == 200:
                     bids = res.json().get('data', {}).get('bids', [])
                     if bids: return float(bids[0]['p'])
            elif ex_name == "LTR":
                 if ticker in ex.ticker_map:
                     mid = ex.ticker_map[ticker]
                     res = await asyncio.get_running_loop().run_in_executor(None, lambda: requests.get(f"https://mainnet.zklighter.elliot.ai/api/v1/orderBook/{mid}", timeout=2))
                     if res.status_code == 200:
                         bids = res.json().get('bids', [])
                         if bids: return float(bids[0]['price'])
        except: pass
        if 'HL' in self.exchanges:
            try:
                hl_mids = self.exchanges['HL'].info.all_mids()
                price = float(hl_mids.get(ticker) or hl_mids.get(f"k{ticker}", 0))
                if price > 0: return price
            except: pass
        return 0.0

    async def find_arbitrage_opportunity(self, symbol):
        if symbol in self.active_positions: return

        data = self.bbo_cache.get(symbol, {})
        if len(data) < 2: return 
        if symbol not in settings.TARGET_PAIRS_CONFIG: return
        
        config = settings.TARGET_PAIRS_CONFIG[symbol]
        preset_name = config.get('strategy_preset', 'major')
        strategy = settings.STRATEGY_PRESETS.get(preset_name, {})
        entry_threshold = strategy.get('entry_threshold_pct', 0.2)
        
        valid_exchanges = list(data.keys())
        best_spread = -999
        best_pair = (None, None)
        
        for long_ex in valid_exchanges:
            for short_ex in valid_exchanges:
                if long_ex == short_ex: continue
                long_p = (data[long_ex]['bid'] + data[long_ex]['ask']) / 2
                short_p = (data[short_ex]['bid'] + data[short_ex]['ask']) / 2
                if long_p <= 0: continue
                spread = (short_p - long_p) / long_p * 100
                if spread > best_spread:
                    best_spread = spread
                    best_pair = (long_ex, short_ex)

        if best_spread > entry_threshold:
            if self._is_in_cooldown(symbol): return
            long_ex, short_ex = best_pair
            log.info(f"✨ [기회] {symbol} Spread:{best_spread:.3f}% (Target > {entry_threshold}%) | Buy:{long_ex} Sell:{short_ex}")
            await self.execute_dual_order(symbol, long_ex, short_ex, best_spread)

    # [핵심] 활성 포지션 모니터링 (시간 & 스프레드 로직 적용)
    async def monitor_active_positions(self):
        if not self.active_positions: return
        
        for symbol, pos in list(self.active_positions.items()):
            # 1. 설정값 로드
            config = settings.TARGET_PAIRS_CONFIG.get(symbol, {})
            preset_name = config.get('strategy_preset', 'major')
            strategy = settings.STRATEGY_PRESETS.get(preset_name, {})
            
            min_hold = strategy.get('min_hold_time_sec', 0)
            max_hold = strategy.get('max_hold_time_sec', 3600) # 기본 1시간
            exit_target = strategy.get('exit_threshold_pct', 0.05)
            
            # 2. 보유 시간 계산
            elapsed = time.time() - pos['time']
            
            # 3. [강제 청산] 최대 보유 시간 초과
            if elapsed > max_hold:
                log.info(f"⏰ [시간 초과] {symbol} {elapsed:.0f}s > {max_hold}s. 강제 청산.")
                await self.close_position(symbol, pos)
                continue

            # 4. 현재가 조회 및 스프레드 계산
            curr_long_p = await self.get_price_robust(pos['long'], symbol)
            curr_short_p = await self.get_price_robust(pos['short'], symbol)
            if curr_long_p <= 0 or curr_short_p <= 0: continue

            curr_spread = (curr_short_p - curr_long_p) / curr_long_p * 100
            pos['current_spread'] = curr_spread
            
            # 5. [청산 보류] 최소 보유 시간 미달이면, 이익이어도 대기
            if elapsed < min_hold:
                # (로그가 너무 많이 뜨지 않도록 디버그 레벨이나 생략 가능)
                # log.debug(f"⏳ {symbol} 최소 시간 대기 중 ({elapsed:.0f}/{min_hold}s)")
                continue
            
            # 6. [정상 익절] 목표 스프레드 도달
            if curr_spread < exit_target:
                log.info(f"📉 [익절 신호] {symbol} Spread:{curr_spread:.3f}% < {exit_target}%")
                await self.close_position(symbol, pos)

    async def close_position(self, symbol, pos):
        log.info(f"🧹 [청산 시작] {symbol} {pos['qty']}개 정리")
        long_ex = self.exchanges[pos['long']]
        short_ex = self.exchanges[pos['short']]
        qty = pos['qty']
        
        p_long = await self.get_price_robust(pos['long'], symbol)
        p_short = await self.get_price_robust(pos['short'], symbol)
        
        task1 = long_ex.place_market_order(symbol, 'SELL', qty, p_long, reduce_only=True)
        task2 = short_ex.place_market_order(symbol, 'BUY', qty, p_short, reduce_only=True)
        
        await asyncio.gather(task1, task2, return_exceptions=True)
        
        log.info(f"✅ [청산 완료] {symbol} 포지션 종료")
        self.pm.log_trade({'Symbol': symbol, 'Type': 'Exit', 'Qty': qty, 'Exchange': f"{pos['long']}/{pos['short']}"})
        
        if symbol in self.active_positions:
            del self.active_positions[symbol]

    def _is_in_cooldown(self, symbol):
        last = self.opportunity_cache.get(symbol, 0)
        return (time.time() - last) < 30 

    async def _check_balance(self, ex_name, required_usd):
        ex = self.exchanges.get(ex_name)
        if not ex: return False
        bal = await ex.get_balance()
        if not bal: return False 
        available = bal.get('available', 0.0)
        if available < required_usd:
            log.warning(f"⚠️ [{ex_name}] 잔고 부족: {available:.2f} < 필요 {required_usd:.2f}")
            return False
        return True

    async def execute_dual_order(self, symbol, long_ex_name, short_ex_name, spread):
        self.opportunity_cache[symbol] = time.time()
        long_price = await self.get_price_robust(long_ex_name, symbol)
        if long_price <= 0: return

        target_lev, qty, pos_usd = self.market_sync.calculate_smart_order_params(symbol, long_price)
        if qty <= 0: return

        required_margin = (pos_usd / target_lev) * 1.05
        if not await self._check_balance(long_ex_name, required_margin): return
        if not await self._check_balance(short_ex_name, required_margin): return

        log.info(f"⚔️ [진입] {symbol} {qty}개 (Lev: x{target_lev})")
        long_ex = self.exchanges[long_ex_name]
        short_ex = self.exchanges[short_ex_name]
        
        await asyncio.gather(
            long_ex.set_leverage(symbol, target_lev),
            short_ex.set_leverage(symbol, target_lev)
        )
        
        short_price = await self.get_price_robust(short_ex_name, symbol)
        
        task1 = long_ex.place_market_order(symbol, 'BUY', qty, long_price)
        task2 = short_ex.place_market_order(symbol, 'SELL', qty, short_price)
        
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        res1, res2 = results
        
        # [추가됨] 주문 후 잔고 동기화를 위해 잠시 대기 (Extended 잔고 랙 방지)
        await asyncio.sleep(2)  # 2초 대기
        
        # 잔고 강제 업데이트 요청 (다음 주문을 위해)
        await self.pm.update_balances()

        success1 = isinstance(res1, dict)
        success2 = isinstance(res2, dict)
        
        if success1 and success2:
            log.info(f"✅ [체결완료] {symbol} Arbitrage 진입 성공!")
            self.active_positions[symbol] = {
                'qty': qty, 'long': long_ex_name, 'short': short_ex_name, 'time': time.time(),
                'entry_spread': spread, 'current_spread': spread
            }
        elif success1 or success2:
            log.critical(f"🚨 [LEGGING] 한쪽만 체결됨! 즉시 청산 실행")
            try:
                if success1: await long_ex.place_market_order(symbol, 'SELL', qty, long_price, reduce_only=True)
                else: await short_ex.place_market_order(symbol, 'BUY', qty, short_price, reduce_only=True)
            except: pass

    def get_market_summary(self):
        if not self.market_sync: return []
        data = []
        for t, c in settings.TARGET_PAIRS_CONFIG.items():
            i = self.market_sync.common_info.get(t, {})
            data.append({
                'Ticker': t, 'Min_Qty': i.get('min_qty'), 
                'Precision': i.get('qty_prec'),
                'Max_Lev': i.get('max_lev'), 'Size($)': c.get('trade_size_fixed_usd')
            })
        return data

if __name__ == "__main__":
    bot = ArbitrageBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        pass