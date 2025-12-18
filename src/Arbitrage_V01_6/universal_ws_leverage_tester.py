import asyncio
import logging
import os
import sys
import time
from dotenv import load_dotenv
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("WS_Tester")

try:
    import settings
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange,
        LighterExchange, ExtendedExchange
    )
except ImportError as e:
    log.error(f"❌ 필수 모듈 임포트 실패: {e}")
    sys.exit(1)

TEST_CONFIG = [
    {"name": "HL", "ticker": "0G", "side": "BUY", "leverage": 3, "total_usd": 45.0},
    {"name": "LTR", "ticker": "0G", "side": "SELL", "leverage": 3, "total_usd": 45.0},
    {"name": "PAC", "ticker": "2Z", "side": "BUY", "leverage": 3, "total_usd": 45.0},
    {"name": "GRVT", "ticker": "AAVE", "side": "BUY", "leverage": 3, "total_usd": 45.0},
    {"name": "EXT", "ticker": "AAVE", "side": "SELL", "leverage": 3, "total_usd": 45.0}
]

# 타겟 티커 목록 추출
TARGET_TICKERS = list(set([c['ticker'] for c in TEST_CONFIG]))
price_cache = {}

async def on_price_update(bbo):
    if not bbo: return
    sym = bbo['symbol']
    ex = bbo['exchange'].upper()
    if ex == 'HYPERLIQUID': ex = 'HL'
    
    if sym not in price_cache: price_cache[sym] = {}
    mid = (bbo['bid'] + bbo['ask']) / 2
    price_cache[sym][ex] = mid

# [수정] 스마트 가격 대기 함수
async def wait_for_prices():
    log.info(f"⏳ 타겟 티커({TARGET_TICKERS}) 가격 수신 대기 중...")
    start_time = time.time()
    
    while time.time() - start_time < 30: # 최대 30초 대기
        all_received = True
        for ticker in TARGET_TICKERS:
            # 해당 티커의 가격이 하나라도 들어왔는지 확인 (거래소 불문)
            if ticker not in price_cache or not price_cache[ticker]:
                all_received = False
                break
        
        if all_received:
            log.info("✅ 모든 타겟 티커 가격 수신 완료!")
            return
        
        await asyncio.sleep(1)
    
    log.warning("⚠️ 일부 티커 가격 수신 실패 (타임아웃). Fallback 사용 예정.")

async def get_price_robust(ex_name, ticker, exchanges):
    # 1. WS Cache 확인
    if ticker in price_cache and ex_name in price_cache[ticker]:
        return price_cache[ticker][ex_name]
    
    # 2. 거래소별 REST API 즉시 조회 (GRVT, LTR, EXT 등)
    ex = exchanges.get(ex_name)
    price = 0.0
    try:
        if ex_name == "GRVT" and ex:
             # GRVT REST Ticker
             t = await ex.grvt.fetch_ticker(f"{ticker}_USDT_Perp")
             price = float(t.get('last') or t.get('close') or 0)
        elif ex_name == "EXT":
             # Extended REST Orderbook
             res = await asyncio.get_running_loop().run_in_executor(None, lambda: requests.get(f"https://api.starknet.extended.exchange/v1/orderbooks/{ticker}-USD"))
             if res.status_code == 200:
                 bids = res.json().get('data', {}).get('bids', [])
                 if bids: price = float(bids[0]['p'])
        # ... (PAC, LTR 등 기존 로직 동일)
    except: pass

    if price > 0: return price

    # 3. 최후의 수단: HL 가격 참조
    if 'HL' in exchanges and exchanges['HL'].info:
        try:
            all_mids = exchanges['HL'].info.all_mids()
            hl_price = float(all_mids.get(ticker, 0) or all_mids.get(f"k{ticker}", 0))
            if hl_price > 0: return hl_price
        except: pass

    return 0.0

async def run_test():
    load_dotenv()
    exchanges = {}
    
    print("\n" + "="*50)
    print("🚀 스마트 레버리지 주문 통합 테스트")
    print("="*50 + "\n")

    log.info("🔌 거래소 연결...")
    if os.getenv('HYPERLIQUID_PRIVATE_KEY'): exchanges['HL'] = HyperliquidExchange(os.getenv('HYPERLIQUID_PRIVATE_KEY'))
    if os.getenv('GRVT_API_KEY'): exchanges['GRVT'] = GrvtExchange()
    if os.getenv('PACIFICA_MAIN_ADDRESS'): exchanges['PAC'] = PacificaExchange(os.getenv('PACIFICA_MAIN_ADDRESS'), os.getenv('PACIFICA_AGENT_PRIVATE_KEY'))
    if os.getenv('LIGHTER_PRIVATE_KEY'): exchanges['LTR'] = LighterExchange(os.getenv('LIGHTER_PRIVATE_KEY'), os.getenv('LIGHTER_WALLET_ADDRESS'))
    if os.getenv('EXTENDED_API_KEY'): exchanges['EXT'] = ExtendedExchange(os.getenv('EXTENDED_PRIVATE_KEY'), os.getenv('EXTENDED_PUBLIC_KEY'), os.getenv('EXTENDED_API_KEY'), os.getenv('EXTENDED_VAULT'))

    log.info("📥 마켓 데이터 로딩...")
    for name, ex in exchanges.items(): await ex.load_markets()

    log.info("📡 WebSocket 시작...")
    ws_tasks = []
    for name, ex in exchanges.items(): ws_tasks.append(asyncio.create_task(ex.start_ws(on_price_update)))

    # [핵심] 스마트 대기
    await wait_for_prices()
    
    print("\n💰 [초기 잔고]")
    for name, ex in exchanges.items():
        bal = await ex.get_balance()
        if bal: print(f"   - {name}: Equity ${bal['equity']:.2f} | Available ${bal.get('available', 0):.2f}")

    print("\n⚔️ [주문 실행]")
    open_orders = []

    for conf in TEST_CONFIG:
        name = conf['name']
        ticker = conf['ticker']
        ex = exchanges.get(name)
        if not ex: continue

        price = await get_price_robust(name, ticker, exchanges)
        if price <= 0:
            log.error(f"❌ [{name}] {ticker} 가격 확인 불가. 주문 스킵.")
            continue

        qty = conf['total_usd'] / price
        
        print(f"\n👉 [{name}] {ticker} {conf['side']} 진입 시도")
        print(f"   - 목표: ${conf['total_usd']} (Price: ${price}) -> Qty: {qty:.4f}")

        await ex.set_leverage(ticker, conf['leverage'])
        res = await ex.place_market_order(ticker, conf['side'], qty, price)
        
        if res:
            log.info(f"   ✅ 주문 성공: {res}")
            open_orders.append({"ex": ex, "name": name, "ticker": ticker, "side": "SELL" if conf['side'] == "BUY" else "BUY", "qty": qty, "price": price})
        else:
            log.error(f"   ❌ 주문 실패")

    print("\n💰 [주문 후 잔고]")
    await asyncio.sleep(2)
    for name, ex in exchanges.items():
        bal = await ex.get_balance()
        if bal:
            pos_str = ", ".join([f"{p['symbol']}:{p['size']}" for p in bal.get('positions', [])])
            print(f"   - {name}: Equity ${bal['equity']:.2f} | Pos: {pos_str}")

    print("\n🧹 [포지션 정리 (청산)]")
    if input(">> 청산? (y/n): ").lower() == 'y':
        for order in open_orders:
            ex = order['ex']
            print(f"👉 [{order['name']}] {order['ticker']} (청산)")
            # [수정] 청산 시에도 수량 검증을 위해 qty 그대로 전달 (API 내부에서 validate_amount 호출됨)
            res = await ex.place_market_order(order['ticker'], order['side'], order['qty'], order['price'], reduce_only=True)
            if res: log.info("   ✅ 청산 성공")
            else: log.error("   ❌ 청산 실패")
    
    log.info("🛑 종료...")
    for ex in exchanges.values(): await ex.close()
    for t in ws_tasks: t.cancel()

if __name__ == "__main__":
    try: asyncio.run(run_test())
    except: pass