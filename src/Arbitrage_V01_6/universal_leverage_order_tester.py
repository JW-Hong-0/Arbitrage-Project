import asyncio
import logging
import os
import sys
import requests
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("UniversalTester")

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
    {"name": "HL", "ticker": "0G", "side": "BUY", "leverage": 3, "margin_usd": 15.0, "total_usd": 45.0},
    {"name": "LTR", "ticker": "0G", "side": "SELL", "leverage": 3, "margin_usd": 15.0, "total_usd": 45.0},
    {"name": "PAC", "ticker": "2Z", "side": "BUY", "leverage": 3, "margin_usd": 15.0, "total_usd": 45.0},
    {"name": "GRVT", "ticker": "AAVE", "side": "BUY", "leverage": 3, "margin_usd": 15.0, "total_usd": 45.0},
    {"name": "EXT", "ticker": "AAVE", "side": "SELL", "leverage": 3, "margin_usd": 15.0, "total_usd": 45.0}
]

# [수정] exchanges dict 인자 추가
async def get_market_price(ex_name, exchange, ticker, exchanges):
    price = 0.0
    try:
        if ex_name == "HL":
            if exchange.info:
                all_mids = exchange.info.all_mids()
                price = float(all_mids.get(ticker, 0) or all_mids.get(f"k{ticker}", 0))
        
        elif ex_name == "GRVT":
            full_sym = f"{ticker}_USDT_Perp"
            t = await exchange.grvt.fetch_ticker(full_sym)
            price = float(t.get('last') or t.get('close') or 0)
            
        elif ex_name == "PAC":
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: requests.get(f"{exchange.url}/info"))
            if res.status_code == 200:
                for d in res.json().get('data', []):
                    if d['symbol'] == ticker:
                        price = float(d.get('mark_price') or d.get('index_price') or 0)
                        break
        
        elif ex_name == "LTR":
            # [수정] 1. REST API로 시도
            if ticker in exchange.ticker_map:
                mid = exchange.ticker_map[ticker]
                url = f"https://mainnet.zklighter.elliot.ai/api/v1/orderBook/{mid}"
                try:
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(None, lambda: requests.get(url, timeout=3))
                    if res.status_code == 200:
                        ob = res.json()
                        bids = ob.get('bids', [])
                        if bids: price = float(bids[0]['price'])
                except: pass
            
            # [핵심] 2. 실패 시 HL 가격 참조 (Cross-Exchange Fallback)
            if price == 0 and 'HL' in exchanges:
                hl_ex = exchanges['HL']
                if hl_ex.info:
                    all_mids = hl_ex.info.all_mids()
                    price = float(all_mids.get(ticker, 0) or all_mids.get(f"k{ticker}", 0))
                    if price > 0:
                        log.info(f"ℹ️ [LTR] 실시간 가격 조회 실패 -> HL 가격(${price}) 참조")

        elif ex_name == "EXT":
            url = f"https://api.starknet.extended.exchange/v1/orderbooks/{ticker}-USD"
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: requests.get(url))
            if res.status_code == 200:
                data = res.json().get('data', {})
                bids = data.get('bids', [])
                if bids:
                    price = float(bids[0]['p'])

    except Exception as e:
        log.warning(f"⚠️ [{ex_name}] 가격 조회 중 에러: {e}")

    if price <= 0:
        # 최후의 수단: 테스트용 하드코딩
        fallback_prices = {"0G": 0.5, "2Z": 0.5} 
        price = fallback_prices.get(ticker, 0.0)
        if price > 0:
            log.warning(f"⚠️ [{ex_name}] {ticker} 가격 조회 실패 -> 기본값(${price}) 사용 (주문 위험)")
            
    return price

async def run_test():
    load_dotenv()
    exchanges = {}
    
    print("\n" + "="*50)
    print("🚀 5대 거래소 레버리지 주문 통합 테스트 (Final)")
    print("="*50 + "\n")

    log.info("🔌 거래소 연결 중...")
    if os.getenv('HYPERLIQUID_PRIVATE_KEY'):
        exchanges['HL'] = HyperliquidExchange(os.getenv('HYPERLIQUID_PRIVATE_KEY'))
    if os.getenv('GRVT_API_KEY'):
        exchanges['GRVT'] = GrvtExchange()
    if os.getenv('PACIFICA_MAIN_ADDRESS'):
        exchanges['PAC'] = PacificaExchange(os.getenv('PACIFICA_MAIN_ADDRESS'), os.getenv('PACIFICA_AGENT_PRIVATE_KEY'))
    if os.getenv('LIGHTER_PRIVATE_KEY'):
        exchanges['LTR'] = LighterExchange(os.getenv('LIGHTER_PRIVATE_KEY'), os.getenv('LIGHTER_WALLET_ADDRESS'))
    if os.getenv('EXTENDED_API_KEY'):
        exchanges['EXT'] = ExtendedExchange(
            os.getenv('EXTENDED_PRIVATE_KEY'), os.getenv('EXTENDED_PUBLIC_KEY'),
            os.getenv('EXTENDED_API_KEY'), os.getenv('EXTENDED_VAULT')
        )

    log.info("📥 마켓 데이터 로딩...")
    for name, ex in exchanges.items():
        await ex.load_markets()

    print("\n💰 [초기 잔고]")
    for name, ex in exchanges.items():
        bal = await ex.get_balance()
        if bal:
            print(f"   - {name}: Equity ${bal['equity']:.2f} | Available ${bal.get('available', 0):.2f}")
        else:
            print(f"   - {name}: 잔고 조회 실패")

    print("\n⚔️ [주문 실행]")
    open_orders = []

    for conf in TEST_CONFIG:
        name = conf['name']
        ticker = conf['ticker']
        ex = exchanges.get(name)
        if not ex: continue

        # [수정] exchanges 전달
        price = await get_market_price(name, ex, ticker, exchanges)
        
        if price <= 0:
            log.error(f"❌ [{name}] {ticker} 가격 확인 불가. 주문 스킵.")
            continue

        qty = conf['total_usd'] / price
        
        print(f"\n👉 [{name}] {ticker} {conf['side']} 진입 시도")
        print(f"   - 목표: ${conf['total_usd']} (Price: ${price}) -> Qty: {qty:.4f}")

        success, final_lev = await ex.set_leverage(ticker, conf['leverage'])
        if success:
            log.info(f"   ✅ 레버리지 x{final_lev} 설정")
        
        res = await ex.place_market_order(ticker, conf['side'], qty, price)
        
        if res:
            log.info(f"   ✅ 주문 성공: {res}")
            open_orders.append({
                "ex": ex, "name": name, "ticker": ticker,
                "side": "SELL" if conf['side'] == "BUY" else "BUY",
                "qty": qty, "price": price
            })
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
    user_input = input(">> 포지션을 정리(청산)하시겠습니까? (y/n): ")
    
    if user_input.lower() == 'y':
        for order in open_orders:
            ex = order['ex']
            print(f"👉 [{order['name']}] {order['ticker']} {order['side']} (청산) - {order['qty']:.4f}개")
            res = await ex.place_market_order(order['ticker'], order['side'], order['qty'], order['price'], reduce_only=True)
            if res: log.info("   ✅ 청산 성공")
            else: log.error("   ❌ 청산 실패")
            
        # [추가] 청산 후 잔고 재확인 (Double Check)
        print("\n🔍 [최종 잔고 확인]")
        await asyncio.sleep(2)
        for name, ex in exchanges.items():
            bal = await ex.get_balance()
            if bal:
                pos_str = ", ".join([f"{p['symbol']}:{p['size']}" for p in bal.get('positions', [])])
                print(f"   - {name}: Equity ${bal['equity']:.2f} | Pos: {pos_str}")
    else:
        print("⚠️ 포지션을 유지한 채 종료합니다.")

    for ex in exchanges.values():
        await ex.close()
    print("\n👋 테스트 완료.")

if __name__ == "__main__":
    asyncio.run(run_test())