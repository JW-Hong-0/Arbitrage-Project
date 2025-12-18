import time
import logging
import sys
import json
import settings
from pacifica_trader import PacificaTrader

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    print("==========================================")
    print("🌊 Pacifica Finance 매매 로직 테스터 🌊")
    print("==========================================")

    # 1. 설정 로드
    try:
        pac_conf = settings.EXCHANGE_CONFIG['pacifica']
        main_addr = pac_conf['main_address']
        agent_key = pac_conf['agent_private_key']
        if not main_addr or not agent_key:
            print("❌ 오류: settings.py 설정 누락")
            return
    except KeyError:
        print("❌ 오류: settings.py에 'pacifica' 항목이 없습니다.")
        return

    # 2. 초기화
    try:
        trader = PacificaTrader(main_address=main_addr, agent_private_key=agent_key)
    except Exception as e:
        print(f"❌ 초기화 중 예외 발생: {e}")
        return

    # 3. 초기 잔고 조회
    print("\n🔍 1. 초기 상태 조회 중...")
    initial_account = trader.get_account_info()
    if initial_account and 'data' in initial_account:
        data = initial_account['data']
        init_equity = float(data.get('account_equity', 0))
        init_margin = float(data.get('total_margin_used', 0))
        print(f"✅ 초기 잔고 확인")
        print(f"   💰 순자산 (Equity): ${init_equity:.4f}")
        print(f"   🔒 사용 중인 마진: ${init_margin:.4f}")
        print(f"   💵 주문 가능 금액: ${data.get('available_to_spend', 'N/A')}")
    else:
        print("❌ 잔고 조회 실패")
        return

    # ---------------------------------------------------------
    # 4. 주문 설정
    # ---------------------------------------------------------
    print("\n======== [주문 설정] ========")
    
    ticker_input = input("🎯 거래할 티커 입력 (BTC 또는 ETH) [기본값: ETH]: ").strip().upper()
    target_ticker = ticker_input if ticker_input else "ETH"
    
    if target_ticker not in trader.market_config:
        print(f"❌ 지원하지 않는 티커입니다. ({list(trader.market_config.keys())})")
        return

    try:
        margin_usd = float(input("💰 투입할 증거금 (USD) [예: 10]: "))
        leverage = int(input("⚡ 계산용 레버리지 (배율) [예: 10]: "))
        
        print(f"\n⚠️ [중요] 봇은 레버리지를 변경하지 않습니다.")
        print(f"   웹사이트에서 '{target_ticker}'의 레버리지가 'x{leverage}'로 설정되어 있는지 꼭 확인하세요!")
        
        print(f"⏳ {target_ticker} 현재가 조회 중 (WebSocket)...")
        current_price = trader.get_current_price(target_ticker)
        
        if current_price <= 0:
            current_price = float(input(f"📊 {target_ticker} 현재가 직접 입력: "))
        else:
            print(f"✅ 현재가 수신 완료: ${current_price:,.2f}")

        # 주문 수량 계산
        target_size_usd = margin_usd * leverage
        calc_qty = target_size_usd / current_price
        
        min_qty = trader.market_config[target_ticker]['min_qty']
        if calc_qty < min_qty:
            print(f"❌ 계산된 수량({calc_qty:.4f})이 최소 주문 수량({min_qty})보다 작습니다.")
            return
            
        print(f"\n[주문 미리보기]")
        print(f" - 티커: {target_ticker}")
        print(f" - 진입가(예상): ${current_price:,.2f}")
        print(f" - 포지션 규모(Notional): ${target_size_usd:.2f} ({leverage}배)")
        print(f" - 예상 필요 마진: ${margin_usd:.2f}")
        print(f" - 주문 수량: {calc_qty:.4f} {target_ticker}")
        
    except ValueError:
        print("❌ 숫자만 입력해주세요.")
        return

    # ---------------------------------------------------------
    # 5. 매수/매도 실행
    # ---------------------------------------------------------
    confirm = input(f"\n🚀 위 설정대로 시장가 매수(Long)를 진행하시겠습니까? (y/n): ")
    
    if confirm.lower() == 'y':
        print(f"\n🚀 [ENTRY] {target_ticker} Long 진입 시도...")
        res = trader.place_market_order(target_ticker, "BUY", calc_qty)
        
        if res:
            print("✅ 진입 주문 요청 완료. 체결 및 잔고 갱신 대기 (3초)...")
            time.sleep(3)
            
            # --- [핵심 추가] 주문 후 잔고 및 포지션 확인 ---
            print("\n📊 [최종 결과 리포트]")
            
            # 1) 포지션 확인
            positions = trader.get_positions()
            current_pos = positions.get(target_ticker)
            
            if current_pos:
                entry_val = current_pos['entry_price'] * current_pos['amount']
                print(f"1️⃣ 포지션 상태 (GET /positions):")
                print(f"   - Side: {current_pos['side']}")
                print(f"   - Amount: {current_pos['amount']} {target_ticker}")
                print(f"   - Entry Price: ${current_pos['entry_price']:.2f}")
                print(f"   - 총 포지션 가치: ${entry_val:.2f}")
            else:
                print(f"1️⃣ 포지션 상태: ⚠️ 조회되지 않음 (체결 실패 가능성)")

            # 2) 계좌 잔고 재확인 (마진 변화 체크)
            final_account = trader.get_account_info()
            if final_account and 'data' in final_account:
                d = final_account['data']
                final_margin = float(d.get('total_margin_used', 0))
                margin_change = final_margin - init_margin
                
                print(f"\n2️⃣ 계좌 잔고 상태 (GET /account):")
                print(f"   💰 순자산 (Equity): ${float(d.get('account_equity', 0)):.4f}")
                print(f"   🔒 총 사용 마진: ${final_margin:.4f} (🔺 +${margin_change:.4f} 증가)")
                print(f"   💵 주문 가능 금액: ${d.get('available_to_spend', 'N/A')}")
                
                if current_pos:
                    print(f"\n✅ 결론: 약 ${margin_change:.2f}의 증거금으로 ${entry_val:.2f} 규모의 포지션을 잡았습니다.")
                    real_leverage = entry_val / margin_change if margin_change > 0 else 0
                    print(f"   (실제 적용된 레버리지: 약 {real_leverage:.1f}배)")

            # 청산 프로세스
            if current_pos:
                confirm_exit = input(f"\n📉 방금 진입한 포지션을 시장가로 정리(청산)하시겠습니까? (y/n): ")
                if confirm_exit.lower() == 'y':
                    print(f"\n📉 [EXIT] {target_ticker} 포지션 정리 시도 (매도)...")
                    exit_qty = current_pos['amount']
                    res_exit = trader.place_market_order(target_ticker, "SELL", exit_qty, reduce_only=True)
                    if res_exit:
                        print("✅ 청산 주문 완료.")
                    else:
                        print("❌ 청산 주문 실패")
        else:
            print(f"❌ 주문 실패")
    
    print("\n🏁 테스트 종료")

if __name__ == "__main__":
    main()