import asyncio
import logging
import sys
import os
import traceback
from dotenv import load_dotenv
import settings
from exchange_apis import (
    HyperliquidExchange, PacificaExchange, 
    LighterExchange, ExtendedExchange, GrvtExchange
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
load_dotenv()

async def main():
    print("==========================================")
    print("🌍 5대 거래소 통합 제어 테스터 (스마트 주문)")
    print("==========================================")
    
    exchanges = {}
    
    # 1. 초기화
    print("1. 거래소 연결 및 마켓 정보 수집 중...")
    
    if os.getenv('HYPERLIQUID_PRIVATE_KEY'):
        exchanges['HL'] = HyperliquidExchange(os.getenv('HYPERLIQUID_PRIVATE_KEY'))
    if os.getenv('PACIFICA_MAIN_ADDRESS'):
        exchanges['PAC'] = PacificaExchange(os.getenv('PACIFICA_MAIN_ADDRESS'), os.getenv('PACIFICA_AGENT_PRIVATE_KEY'))
    if os.getenv('GRVT_API_KEY'):
        exchanges['GRVT'] = GrvtExchange()
    if os.getenv('LIGHTER_PRIVATE_KEY'):
        exchanges['LTR'] = LighterExchange(os.getenv('LIGHTER_PRIVATE_KEY'), os.getenv('LIGHTER_WALLET_ADDRESS'))
    if os.getenv('EXTENDED_API_KEY'):
        exchanges['EXT'] = ExtendedExchange(
            os.getenv('EXTENDED_PRIVATE_KEY'), os.getenv('EXTENDED_PUBLIC_KEY'),
            os.getenv('EXTENDED_API_KEY'), os.getenv('EXTENDED_VAULT')
        )
    
    # 병렬 로드
    tasks = [ex.load_markets() for ex in exchanges.values()]
    await asyncio.gather(*tasks)
    print("✅ 모든 거래소 준비 완료!\n")

    # [추가] 가격 수신용 웹소켓 리스너
    latest_prices = {}
    async def price_callback(bbo):
        latest_prices[bbo['exchange']] = bbo['bid'] # 단순화: 매수호가 저장

    # 웹소켓 시작 (백그라운드)
    # 실제로는 각 거래소별 구현이 필요하지만, 여기서는 REST API로 대체하거나 
    # 테스터에서 임의 가격을 사용하지 않고 사용자에게 입력받거나, 
    # exchange 객체의 get_bbo(미구현시 fetch_ticker 등)를 활용해야 함.
    # -> 가장 확실한 방법: place_market_order 내부에서 현재가를 조회하도록 exchange_apis.py가 수정되었으므로,
    #    테스터에서는 price=None으로 보내면 됩니다.

    while True:
        print("\n[메뉴] 1.전체잔고  2.주문(매수/매도)  3.청산(ReduceOnly)  q.종료")
        try:
            cmd = await asyncio.get_running_loop().run_in_executor(None, input, ">> 선택: ")
        except EOFError: break
        
        if cmd == 'q': break
        
        # 1. 잔고 조회
        if cmd == '1':
            print("\n📊 [통합 잔고 현황]")
            for name, ex in exchanges.items():
                try:
                    bal = await ex.get_balance()
                    if bal:
                        print(f"   - {name}: Equity ${bal['equity']:.2f}")
                        for p in bal['positions']:
                            print(f"     └ {p['symbol']}: {p['side']} {p['size']}")
                    else:
                        print(f"   - {name}: 조회 실패")
                except Exception as e:
                    print(f"   - {name}: 에러 ({e})")
        
        # 2. 일반 주문 (Open)
        elif cmd == '2':
            line = await asyncio.get_running_loop().run_in_executor(None, input, ">> 주문 (예: HL ETH 매수 0.01): ")
            try:
                parts = line.split()
                if len(parts) != 4: continue
                ex_name, sym, side_kor, amt = parts
                
                side = 'BUY' if side_kor == '매수' else ('SELL' if side_kor == '매도' else side_kor.upper())
                ex = exchanges.get(ex_name.upper())
                
                if ex:
                    print(f"🚀 {ex_name} {sym} {side} {amt} (Open) 전송...")
                    
                    # [핵심] price=None으로 전달 -> 거래소 클래스가 알아서 현재가 조회
                    # (단, Lighter/Extended 등은 내부적으로 현재가를 조회하거나 안전한 가격을 써야 함)
                    # 만약 내부 조회가 없다면, 여기서 입력받는게 안전함.
                    
                    # Extended를 위해 가격을 직접 입력받을 수도 있음
                    # 하지만 편의상 None으로 보내고 exchange_apis.py가 처리하게 함.
                    # (ExtendedExchange의 place_market_order에서 price가 None이면 100000/1000을 쓰는데, 
                    #  이게 Price Band에 걸리므로, 이번에는 exchange_apis.py를 믿지 않고 직접 3050 정도를 넣어줌)
                    
                    # 테스트용 하드코딩 (현재 시세 반영)
                    price = 3060.0 if 'ETH' in sym else 95000.0 # ETH 3060불 가정
                    
                    await ex.place_market_order(sym, side, float(amt), price, reduce_only=False)
            except: traceback.print_exc()

        # 3. 청산 주문 (Reduce Only)
        elif cmd == '3':
            line = await asyncio.get_running_loop().run_in_executor(None, input, ">> 청산 (예: HL ETH 매도 0.01): ")
            try:
                parts = line.split()
                if len(parts) != 4: continue
                ex_name, sym, side_kor, amt = parts
                
                side = 'BUY' if side_kor == '매수' else ('SELL' if side_kor == '매도' else side_kor.upper())
                ex = exchanges.get(ex_name.upper())
                
                if ex:
                    print(f"📉 {ex_name} {sym} {side} {amt} (ReduceOnly) 전송...")
                    price = 3060.0 if 'ETH' in sym else 95000.0
                    await ex.place_market_order(sym, side, float(amt), price, reduce_only=True)
            except: traceback.print_exc()

    for ex in exchanges.values():
        if hasattr(ex, 'close'): await ex.close()

if __name__ == "__main__":
    asyncio.run(main())