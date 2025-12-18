import asyncio
import logging
import json
import os
import sys
import traceback
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

# --- 환경 설정 로드 ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- GRVT SDK 임포트 ---
try:
    from pysdk.grvt_ccxt_ws import GrvtCcxtWS
    from pysdk.grvt_ccxt_env import GrvtEnv
except ImportError:
    print("❌ 'pysdk' 모듈을 찾을 수 없습니다.")
    sys.exit(1)

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [GRVT] - %(message)s',
    datefmt='%H:%M:%S'
)
logging.getLogger("pysdk").setLevel(logging.ERROR)
logging.getLogger("GrvtCcxtWS").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

logger = logging.getLogger("GrvtTester")

# --- 설정 ---
TEST_LEVERAGE = 10  # 테스트용 레버리지 (10배)

class GrvtTester:
    def __init__(self):
        self.api_key = os.getenv("GRVT_API_KEY")
        self.private_key = os.getenv("GRVT_PRIVATE_KEY") or os.getenv("GRVT_SECRET_KEY")
        self.sub_account_id = os.getenv("GRVT_TRADING_ACCOUNT_ID")
        
        missing = []
        if not self.api_key: missing.append("GRVT_API_KEY")
        if not self.private_key: missing.append("GRVT_PRIVATE_KEY")
        if not self.sub_account_id: missing.append("GRVT_TRADING_ACCOUNT_ID")
        
        if missing:
            logger.error(f"❌ 설정 누락: {', '.join(missing)}")
            sys.exit(1)

        self.symbol = "BTC_USDT_Perp" 
        self.ws = None

    async def connect(self):
        try:
            params = {
                'api_key': self.api_key,
                'private_key': self.private_key,
                'trading_account_id': self.sub_account_id
            }
            
            loop = asyncio.get_running_loop()
            quiet_logger = logging.getLogger("quiet")
            quiet_logger.setLevel(logging.ERROR)
            
            self.ws = GrvtCcxtWS(
                env=GrvtEnv.PROD,
                loop=loop,
                logger=quiet_logger,
                parameters=params
            )
            
            logger.info("🔌 GRVT 연결 시도...")
            await self.ws.initialize()
            await self.ws.load_markets()
            logger.info("✅ GRVT API 연결 성공!")

        except Exception as e:
            logger.error(f"연결 실패: {e}")
            sys.exit(1)

    def _get_market_info(self):
        """최소 주문 수량 조회"""
        try:
            if self.ws.markets and self.symbol in self.ws.markets:
                market = self.ws.markets[self.symbol]
                min_size = float(market.get('min_size') or market.get('limits', {}).get('amount', {}).get('min', 0.001))
                return min_size
        except:
            pass
        return 0.001

    def _amount_to_precision(self, amount):
        try:
            min_size = self._get_market_info()
            tick = Decimal(str(min_size))
            d_amt = Decimal(str(amount))
            return float((d_amt / tick).quantize(1, rounding=ROUND_DOWN) * tick)
        except:
            return amount

    async def get_price(self):
        try:
            if hasattr(self.ws, 'fetch_ticker'):
                ticker = await self.ws.fetch_ticker(self.symbol)
                if 'last_price' in ticker: return float(ticker['last_price'])
                if 'mark_price' in ticker: return float(ticker['mark_price'])
                if 'last' in ticker: return float(ticker['last'])
            
            ob = await self.ws.fetch_order_book(self.symbol, limit=1)
            if ob.get('bids') and ob.get('asks'):
                bid = float(ob['bids'][0][0] if isinstance(ob['bids'][0], list) else ob['bids'][0]['price'])
                ask = float(ob['asks'][0][0] if isinstance(ob['asks'][0], list) else ob['asks'][0]['price'])
                return (bid + ask) / 2
            return 0.0
        except:
            return 0.0

    async def print_status(self):
        logger.info("📊 상태 조회 중...")
        try:
            balance = await self.ws.fetch_balance()
            total = float(balance.get('USDT', {}).get('total', 0.0))
            free = float(balance.get('USDT', {}).get('free', 0.0))
            
            print(f"\n======== [ GRVT 자산 현황 ] ========")
            print(f"💰 총 자산 (Equity) : ${total:,.2f}")
            print(f"💵 주문 가능 (Free)  : ${free:,.2f}")
            print(f"⚙️  테스트 레버리지  : {TEST_LEVERAGE}x")
            print(f"====================================")

            positions = await self.ws.fetch_positions([self.symbol])
            has_pos = False
            for pos in positions:
                sym = pos.get('symbol') or pos.get('instrument')
                if sym == self.symbol:
                    size = float(pos.get('contracts') or pos.get('size') or 0)
                    if size != 0:
                        has_pos = True
                        side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                        entry = float(pos.get('entryPrice') or pos.get('entry_price') or 0)
                        pnl = float(pos.get('unrealizedPnl') or pos.get('unrealized_pnl') or 0)
                        
                        # 레버리지로 인한 실제 증거금 추산
                        margin_used = (abs(size) * entry) / TEST_LEVERAGE # 단순 참고용
                        print(f"Coin: BTC   | {side} | Size: {size:.4f} BTC")
                        print(f"Entry: ${entry:,.2f} | PnL: ${pnl:,.2f} | Est.Margin: ${margin_used:,.2f}")
            
            if not has_pos:
                print("보유 중인 포지션이 없습니다.")
            print("====================================\n")

        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")

    async def print_execution_details(self):
        logger.info("🔍 체결 확인 중...")
        for i in range(5):
            await asyncio.sleep(1)
            try:
                response = await self.ws.fetch_my_trades(self.symbol, limit=5)
                trades = response.get('result', []) if isinstance(response, dict) else response
                if not trades: continue

                trades.sort(key=lambda x: int(x.get('time_created') or x.get('timestamp') or 0))
                last_trade = trades[-1] 
                
                trade_ts = int(last_trade.get('time_created') or last_trade.get('timestamp') or 0)
                if trade_ts > 10000000000000: trade_ts /= 1000000 
                elif trade_ts > 10000000000: trade_ts /= 1000 

                if (datetime.now().timestamp() * 1000) - trade_ts > 10000:
                     continue

                exec_price = float(last_trade.get('price') or 0)
                exec_qty = float(last_trade.get('size') or last_trade.get('amount') or 0)
                side = (last_trade.get('side') or 'UNKNOWN').upper()
                fee = float(last_trade.get('fee') or last_trade.get('fee_amount') or 0)
                raw_info = last_trade.get('info', {})
                realized_pnl = float(raw_info.get('realized_pnl') or raw_info.get('rp') or 0)
                
                # 주문 가치(Notional) 계산
                notional = exec_price * exec_qty
                # 실제 사용된 마진(증거금) 추산
                used_margin = notional / TEST_LEVERAGE

                print(f"\n✅ [체결 리포트]")
                print(f"   - 시간: {datetime.fromtimestamp(trade_ts/1000).strftime('%H:%M:%S')}")
                print(f"   - 방향: {side}")
                print(f"   - 가격: ${exec_price:,.2f}")
                print(f"   - 수량: {exec_qty} BTC (가치: ${notional:,.2f})")
                print(f"   - 내돈(Est): ${used_margin:,.2f} (Lev {TEST_LEVERAGE}x)")
                print(f"   - 수수료: ${fee:.4f}")
                
                if realized_pnl != 0:
                    pnl_icon = "💰" if realized_pnl > 0 else "💸"
                    print(f"   - 실현 PnL: {pnl_icon} ${realized_pnl:,.4f}")
                print(f"----------------------------------\n")
                return

            except Exception:
                pass
        
        logger.warning("체결 내역 조회 지연")

    async def place_smart_order(self, side_input, amount_input):
        """
        금액($) 입력 시 -> 내 돈(Margin)으로 간주하고 레버리지를 곱해 주문
        수량(BTC) 입력 시 -> 그대로 주문
        """
        try:
            side = 'buy' if side_input == 'buy' else 'sell'
            price = await self.get_price()
            min_size = self._get_market_info()

            is_usd_mode = amount_input > 2.0 
            
            qty = 0.0
            if is_usd_mode:
                if price == 0:
                    logger.error("❌ 현재가 조회 실패. 금액 주문 불가.")
                    return
                
                # [수정된 로직]
                # 입력값($10) = 내 증거금(Margin)
                # 주문규모(Notional) = 증거금 * 레버리지
                margin_amount = amount_input
                target_notional = margin_amount * TEST_LEVERAGE
                raw_qty = target_notional / price
                
                logger.info(f"💵 입력 증거금: ${margin_amount} (x{TEST_LEVERAGE}) -> 목표 주문액: ${target_notional}")
                logger.info(f"   -> 환산 수량: {raw_qty:.6f} BTC (@ ${price:,.0f})")
                
                qty = self._amount_to_precision(raw_qty)
                
                if qty < min_size:
                    req_notional = min_size * price
                    req_margin = req_notional / TEST_LEVERAGE
                    logger.error(f"❌ 주문 불가: 최소 주문 수량({min_size} BTC, 약 ${req_notional:,.2f}) 미달")
                    logger.warning(f"💡 {TEST_LEVERAGE}배 기준, 최소 약 ${req_margin:,.2f} 이상 입력해야 합니다.")
                    return
            else:
                raw_qty = amount_input
                logger.info(f"🔢 입력 수량: {raw_qty} BTC")
                qty = self._amount_to_precision(raw_qty)

            if qty == 0:
                logger.error("❌ 수량 오류: 0 BTC")
                return

            logger.info(f"🚀 주문 전송: {side.upper()} {qty} BTC (Market)")
            
            order = await self.ws.create_order(
                symbol=self.symbol,
                order_type='market',
                side=side,
                amount=qty
            )
            
            if order:
                logger.info(f"✅ 주문 접수 완료")
                await self.print_execution_details()
                await self.print_status()
            else:
                logger.error("❌ 주문 실패")

        except Exception as e:
            logger.error(f"주문 오류: {e}")
            traceback.print_exc()

    async def close_all_positions(self):
        logger.info("🚨 청산 시도...")
        try:
            await self.ws.cancel_all_orders(self.symbol)
            
            positions = await self.ws.fetch_positions([self.symbol])
            target_pos = None
            for p in positions:
                sym = p.get('symbol') or p.get('instrument')
                if sym == self.symbol:
                    sz = float(p.get('contracts') or p.get('size') or 0)
                    if sz != 0:
                        target_pos = p
                        break
            
            if not target_pos:
                logger.info("청산할 포지션 없음.")
                return

            size = float(target_pos.get('contracts') or target_pos.get('size'))
            side = 'sell' if size > 0 else 'buy'
            abs_size = abs(size)
            
            logger.info(f"🔄 청산 주문: {side.upper()} {abs_size} BTC (Market)")
            
            await self.ws.create_order(
                symbol=self.symbol,
                order_type='market',
                side=side,
                amount=abs_size,
                params={'reduceOnly': True}
            )
            
            logger.info("✅ 청산 주문 전송 완료")
            await self.print_execution_details()
            await self.print_status()

        except Exception as e:
            logger.error(f"청산 오류: {e}")

    async def run_console(self):
        await self.connect()
        print(f"\n🎮 GRVT Smart Tester 준비 완료 (Lev {TEST_LEVERAGE}x 적용)")
        print("명령어 예시: '잔고', '매수 10'(증거금 $10), '매수 0.001', '청산'")
        
        while True:
            try:
                loop = asyncio.get_running_loop()
                cmd = await loop.run_in_executor(None, input, ">> 명령: ")
                cmd = cmd.strip()
                if not cmd: continue
                if cmd == "exit": break
                
                if cmd == "잔고":
                    await self.print_status()
                elif cmd.startswith("매수"):
                    parts = cmd.split()
                    if len(parts) == 2: await self.place_smart_order('buy', float(parts[1]))
                    else: print("형식: 매수 [금액/수량]")
                elif cmd.startswith("매도"):
                    parts = cmd.split()
                    if len(parts) == 2: await self.place_smart_order('sell', float(parts[1]))
                    else: print("형식: 매도 [금액/수량]")
                elif cmd == "청산":
                    await self.close_all_positions()
                else:
                    print("알 수 없는 명령어")
            except Exception as e:
                logger.error(f"오류: {e}")

    async def close(self):
        logger.info("종료 중...")

async def main():
    tester = GrvtTester()
    try:
        await tester.run_console()
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())