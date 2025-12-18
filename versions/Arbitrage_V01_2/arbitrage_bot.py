import asyncio
import sys
import os
import logging
import time
import uuid
import pandas as pd
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
log = logging.getLogger("ArbitrageBot")

class ArbitrageBot:
    def __init__(self, loop=None):
        self.loop = loop if loop else asyncio.get_event_loop()
        self.is_running = False
        self.start_time = 0 

        # 쿨타임 관리 (티커별 재진입 대기 시간)
        self.cooldowns = {}
        self.COOLDOWN_SECONDS = 300 
        
        # [신규] 연속 틱 검증을 위한 카운터
        self.opp_counters = defaultdict(int)
        self.REQUIRED_CONFIRMATIONS = 3  # 3회 연속 포착 시 진입 (약 0.3초)
        
        self.exchanges = {
            'hyperliquid': HyperliquidExchange(os.getenv("HL_PRIVATE_KEY"), os.getenv("HL_ACCOUNT_ADDRESS")),
            'grvt': GrvtExchange(os.getenv("GRVT_API_KEY"), os.getenv("GRVT_SECRET_KEY"), os.getenv("GRVT_TRADING_ACCOUNT_ID")),
            'pacifica': PacificaExchange(os.getenv("PACIFICA_PRIVATE_KEY"), os.getenv("PACIFICA_ADDRESS")),
            'extended': ExtendedExchange(os.getenv("EXTENDED_PRIVATE_KEY"), os.getenv("EXTENDED_ADDRESS")),
            'lighter': LighterExchange(os.getenv("LIGHTER_API_KEY"), os.getenv("LIGHTER_PUBLIC_KEY"))
        }

        init_balances = settings.SIMULATION_CONFIG.get('INITIAL_BALANCES', {})
        fees = settings.SIMULATION_CONFIG.get('FEES', {})
        self.fees = fees
        self.recorder = PortfolioManager() 
        self.virtual_portfolio = VirtualPortfolioManager(init_balances, fees, self.recorder)
        
        self.market_cache = defaultdict(dict)
        self.cache_lock = asyncio.Lock()
        self.based_config = getattr(settings, 'BASED_APP_CONFIG', {})
        
        self.max_concurrent_positions = 5

    async def _on_market_data(self, data: Dict):
        ticker = data.get('symbol')
        exchange = data.get('exchange')
        if not ticker or not exchange: return
        current_time = time.time()
        async with self.cache_lock:
            self.market_cache[ticker][exchange] = {
                'bid': float(data['bid']),
                'ask': float(data['ask']),
                'timestamp': current_time 
            }

    async def _monitor_market_loop(self):
        log.info("🚀 차익거래 전략 엔진 가동 (안전 모드 ON)...")
        
        WARMUP_DURATION = 30
        while self.is_running:
            elapsed = time.time() - self.start_time
            if elapsed < WARMUP_DURATION:
                remaining = int(WARMUP_DURATION - elapsed)
                if remaining % 5 == 0:
                    log.info(f"🔥 시스템 예열 중... 데이터 수집 및 안정화 단계 ({remaining}초 남음)")
                await asyncio.sleep(1)
                continue
                
            try:
                await self._execute_strategy_logic()
            except Exception as e:
                log.error(f"전략 루프 에러: {e}")
            
            await asyncio.sleep(0.1)

    async def _execute_strategy_logic(self):
        current_time = time.time()
        async with self.cache_lock:
            snapshot = self.market_cache.copy()

        target_coins = list(settings.TARGET_PAIRS_CONFIG.keys())
        
        open_positions_count = 0
        for ex_pos in self.virtual_portfolio.positions.values():
            open_positions_count += len(ex_pos)

        for ticker in target_coins:
            if ticker not in snapshot: continue

            active_pos = self.virtual_portfolio.get_active_position(ticker)
            
            # 쿨타임 체크
            last_exit = self.cooldowns.get(ticker, 0)
            if time.time() - last_exit < self.COOLDOWN_SECONDS:
                continue

            # 포지션이 있으면 청산 로직으로
            if active_pos:
                await self._check_exit_condition(ticker, active_pos, snapshot[ticker], current_time)
                continue
            
            # 최대 포지션 수 제한
            if open_positions_count >= (self.max_concurrent_positions * 2): 
                continue

            exchanges_data = snapshot[ticker]
            
            # 1. 유효 데이터 필터링 (타임스탬프 2초 이내)
            valid_data = {
                ex: d for ex, d in exchanges_data.items()
                if current_time - d['timestamp'] < 2.0 
            }
            
            if len(valid_data) < 2: 
                self.opp_counters[ticker] = 0
                continue 

            # 2. [신규] Outlier 필터링 (평균가 대비 3% 이상 괴리 시 제외)
            all_mids = [(d['bid'] + d['ask']) / 2 for d in valid_data.values()]
            avg_price = sum(all_mids) / len(all_mids)
            
            filtered_data = {}
            for ex, d in valid_data.items():
                mid = (d['bid'] + d['ask']) / 2
                # 평균에서 3% 이내인 데이터만 사용
                if abs(mid - avg_price) / avg_price < 0.03:
                    filtered_data[ex] = d
            
            if len(filtered_data) < 2:
                self.opp_counters[ticker] = 0
                continue

            # 3. 최적 호가 찾기 (필터링된 데이터 사용)
            best_buy_ex = min(filtered_data, key=lambda x: filtered_data[x]['ask'])
            best_sell_ex = max(filtered_data, key=lambda x: filtered_data[x]['bid'])
            
            best_buy_price = filtered_data[best_buy_ex]['ask']
            best_sell_price = filtered_data[best_sell_ex]['bid']

            if best_buy_ex == best_sell_ex or best_buy_price >= best_sell_price:
                self.opp_counters[ticker] = 0
                continue

            spread_pct = ((best_sell_price - best_buy_price) / best_buy_price) * 100
            
            # 설정값 로드
            target_cfg = settings.TARGET_PAIRS_CONFIG[ticker]
            preset_name = target_cfg.get('strategy_preset', 'volatile')
            preset = settings.STRATEGY_PRESETS.get(preset_name, settings.STRATEGY_PRESETS['volatile'])
            
            # 수수료 계산
            fee_buy = self.fees.get(best_buy_ex, 0.0005) * 100
            fee_sell = self.fees.get(best_sell_ex, 0.0005) * 100
            total_fee_pct = (fee_buy + fee_sell) * 2 
            
            min_required_spread = max(preset['entry_threshold_pct'], total_fee_pct + 0.1)
            
            # 4. 진입 판단 및 연속성 검증
            if spread_pct > min_required_spread:
                # 기회 포착! 카운트 증가
                self.opp_counters[ticker] += 1
                
                # [핵심] N번 연속 포착되었을 때만 진입
                if self.opp_counters[ticker] >= self.REQUIRED_CONFIRMATIONS:
                    log.info(f"⚡ [기회확정] {ticker} Spread:{spread_pct:.2f}% (유지:{self.opp_counters[ticker]}회) | {best_buy_ex}->{best_sell_ex}")
                    
                    await self._execute_virtual_dual_leg(
                        ticker, best_buy_ex, best_buy_price, best_sell_ex, best_sell_price,
                        target_cfg['trade_size_fixed_usd'], spread_pct
                    )
                    
                    # 진입 후 카운트 초기화 및 쿨타임 적용
                    self.opp_counters[ticker] = 0
                    self.cooldowns[ticker] = time.time()
            else:
                # 기회가 사라지면 카운트 즉시 초기화
                self.opp_counters[ticker] = 0

    async def _check_exit_condition(self, ticker, pos, market_data, current_time):
        hold_time = current_time - pos['long']['data']['entry_time']
        min_hold = getattr(settings, 'POSITION_MIN_HOLD_SECONDS', 180)
        
        long_ex = pos['long']['ex']
        short_ex = pos['short']['ex']

        if long_ex not in market_data or short_ex not in market_data: return

        exit_bid = market_data[long_ex]['bid']
        exit_ask = market_data[short_ex]['ask']

        current_spread = ((exit_ask - exit_bid) / exit_bid) * 100
        
        entry_val = pos['long']['data']['price'] * pos['long']['data']['qty']
        pnl_long = (exit_bid - pos['long']['data']['price']) * pos['long']['data']['qty']
        pnl_short = (pos['short']['data']['price'] - exit_ask) * pos['short']['data']['qty']
        total_pnl = pnl_long + pnl_short 
        net_pnl = total_pnl - (entry_val * 0.001) 
        roi_pct = (net_pnl / entry_val) * 100 if entry_val > 0 else 0

        target_cfg = settings.TARGET_PAIRS_CONFIG[ticker]
        preset = settings.STRATEGY_PRESETS.get(target_cfg.get('strategy_preset', 'volatile'), settings.STRATEGY_PRESETS['volatile'])
        
        should_exit = False
        reason = ""
        
        exit_threshold = preset.get('exit_threshold_pct', 0.0)

        if current_spread <= exit_threshold:
            should_exit = True; reason = f"🎯 목표달성({current_spread:.2f}%)"
        elif roi_pct < -10.0: 
            should_exit = True; reason = "💧 강제손절"
        elif hold_time > settings.POSITION_MAX_HOLD_SECONDS:
            should_exit = True; reason = "⏰ 타임컷"

        if should_exit and reason.startswith("🎯") and hold_time < min_hold:
            return 

        if should_exit:
            log.info(f"👋 [청산-{reason}] {ticker} Spread:{current_spread:.2f}% PnL:${net_pnl:.2f}({roi_pct:.2f}%) Time:{int(hold_time)}s")
            self.virtual_portfolio.add_trade(long_ex, ticker, 'SELL', exit_bid, pos['long']['data']['qty'], 'EXIT', pnl=pnl_long)
            self.virtual_portfolio.add_trade(short_ex, ticker, 'BUY', exit_ask, pos['short']['data']['qty'], 'EXIT', pnl=pnl_short)
            self.cooldowns[ticker] = time.time()

    async def _execute_virtual_dual_leg(self, ticker, buy_ex, buy_price, sell_ex, sell_price, usd_margin, spread_pct):
        leverage = settings.SIMULATION_CONFIG.get('VIRTUAL_LEVERAGE', 1.0)
        target_notional = usd_margin * leverage
        
        buy_qty = target_notional / buy_price
        sell_qty = target_notional / sell_price

        if not self.virtual_portfolio.can_afford(buy_ex, buy_price, buy_qty): return
        if not self.virtual_portfolio.can_afford(sell_ex, sell_price, sell_qty): return

        log.info(f"🚀 [진입확정] {ticker} Spread:{spread_pct:.2f}% | {buy_ex} -> {sell_ex}")

        if self.based_config.get('ENABLED'):
            if buy_ex == 'hyperliquid': self._log_based_order(ticker, 'BUY', buy_price, buy_qty)
            if sell_ex == 'hyperliquid': self._log_based_order(ticker, 'SELL', sell_price, sell_qty)

        self.virtual_portfolio.add_trade(buy_ex, ticker, 'BUY', buy_price, buy_qty, 'ENTRY')
        self.virtual_portfolio.add_trade(sell_ex, ticker, 'SELL', sell_price, sell_qty, 'ENTRY')

    def _log_based_order(self, ticker, side, price, qty):
        pass 

    def save_excel(self):
        try:
            current_balances = self.virtual_portfolio.balances
            self.recorder.export_trade_log_to_excel(balances=current_balances)
        except Exception as e:
            log.error(f"엑셀 저장 요청 실패: {e}")

    async def start(self):
        self.is_running = True
        self.start_time = time.time()
        tasks = [ex.start_ws(self._on_market_data) for ex in self.exchanges.values()]
        tasks.append(self._monitor_market_loop())
        await asyncio.gather(*tasks)

    async def stop(self):
        self.is_running = False
        for ex in self.exchanges.values(): await ex.close()