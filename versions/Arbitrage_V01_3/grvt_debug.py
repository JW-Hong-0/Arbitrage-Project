import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

try:
    import settings
except ImportError:
    settings = None

from exchange_apis import GrvtExchange

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger("GRVT_DEBUG")

def get_config_variable(var_names):
    load_dotenv()
    for name in var_names:
        if settings and hasattr(settings, name):
            val = getattr(settings, name)
            if val: return val
        val = os.getenv(name)
        if val: return val
    return None

async def main():
    log.info("🔍 환경 변수 스캔 중...")

    api_key = get_config_variable(['GRVT_API_KEY'])
    private_key = get_config_variable(['GRVT_PRIVATE_KEY', 'GRVT_SECRET_KEY'])
    sub_account_id = get_config_variable(['GRVT_SUB_ACCOUNT_ID', 'GRVT_TRADING_ACCOUNT_ID', 'GRVT_ACCOUNT_ID'])

    if not (api_key and private_key and sub_account_id):
        log.error("❌ 키를 찾을 수 없습니다.")
        return

    grvt = GrvtExchange(api_key, private_key, sub_account_id)
    
    try:
        log.info("🔌 GRVT 연결 시도...")
        connected = await grvt.connect()
        if not connected:
            log.error("❌ 연결 실패")
            return
        
        log.info("✅ API 연결 및 마켓 데이터 로드 성공")
        await asyncio.sleep(2)

        # 1. 잔고 확인
        balance = await grvt.get_balance()
        if balance:
            log.info(f"💰 현재 잔고: {balance.get('equity')} USDT")
            
            # 기존 포지션 정리
            positions = balance.get('positions', [])
            target_symbol = "BTC_USDT_Perp"
            
            for pos in positions:
                # size 키는 이제 exchange_apis.py에서 보장됨
                p_size = float(pos.get('size', 0))
                if target_symbol in pos.get('instrument', '') and p_size != 0:
                    log.warning(f"⚠️ 기존 포지션 발견 ({p_size}), 정리 시도...")
                    await grvt.close_position(target_symbol)
                    await asyncio.sleep(3)

            # 2. 테스트 진입
            log.info(f"🧪 [테스트 진입] {target_symbol} 0.001 BTC 매수 시도")
            
            order = await grvt.create_order(target_symbol, 'buy', None, 0.001, order_type='MARKET')
            if order:
                log.info(f"🚀 주문 전송 성공! (ID: {order.get('client_order_id') or order.get('id')})")
            else:
                log.error("❌ 주문 실패")
                return

            # [핵심 수정] 포지션 반영 대기 (Polling)
            log.info("⏳ 체결 결과 확인 중 (최대 10초 대기)...")
            detected_pos = None
            
            for i in range(10): # 1초씩 10번 확인
                await asyncio.sleep(1)
                
                # 디버깅을 위해 로우 데이터 확인
                raw_positions = await grvt.ws.fetch_positions()
                # log.info(f"🔍 DEBUG RAW: {raw_positions}") # 필요시 주석 해제하여 확인
                
                bal = await grvt.get_balance()
                current_positions = bal.get('positions', [])
                
                for p in current_positions:
                    if target_symbol in p.get('instrument', '') and float(p.get('size', 0)) != 0:
                        detected_pos = p
                        break
                
                if detected_pos:
                    log.info(f"🎉 포지션 포착 성공! ({i+1}초 소요)")
                    break
            
            if detected_pos:
                size_to_close = float(detected_pos.get('size', 0))
                log.info(f"📊 현재 보유량: {size_to_close} BTC")
                log.info(f"🧹 [청산] 전량 청산 시도")
                await grvt.close_position(target_symbol)
                log.info("✅ 청산 명령 전송 완료")
            else:
                log.warning("⚠️ 10초 대기 후에도 포지션이 보이지 않습니다. (웹소켓 지연 가능성)")
                # 강제 청산 시도 (혹시 모르니)
                log.info("🧹 강제 청산 시도 (블라인드)")
                await grvt.create_order(target_symbol, 'sell', None, 0.001, order_type='MARKET', reduce_only=True)

    except Exception as e:
        log.error(f"❌ 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        log.info("🔌 연결 종료 중...")
        await grvt.close()
        log.info("👋 종료 완료")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())