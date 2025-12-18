import asyncio
import logging
import os
import time
import random
from hyperliquid.utils import constants as hl_constants
from exchange_apis import HyperliquidExchange, log  # 기존 파일 로드

# HyENA 설정
HYENA_BUILDER_ADDRESS = "0x1924b8561eeF20e70Ede628A296175D358BE80e5"
HYENA_BUILDER_FEE = 0

class HyenaExchange(HyperliquidExchange):
    def __init__(self, private_key: str):
        super().__init__(private_key)
        self.builder_address = HYENA_BUILDER_ADDRESS
        self.builder_fee = HYENA_BUILDER_FEE
        log.info(f"🦁 [HyENA] 선물(Perp) 모드 초기화 (Builder: {self.builder_address[:6]}...)")

    async def set_leverage(self, symbol: str, leverage: int):
        """
        레버리지 설정 (Cross Margin 기준)
        """
        try:
            # Hyperliquid SDK의 update_leverage 사용
            log.info(f"⚙️ [HyENA] {symbol} 레버리지 {leverage}x 설정 시도...")
            self.exchange.update_leverage(leverage, symbol, is_cross=True)
            log.info(f"✅ [HyENA] {symbol} 레버리지 {leverage}x 설정 성공")
            return True
        except Exception as e:
            # 아직 상장되지 않은 코인은 에러가 발생함 (스나이핑 시 자연스러운 현상)
            if "Asset not found" not in str(e):
                log.error(f"❌ [HyENA] 레버리지 설정 실패: {e}")
            return False

    async def place_hyena_perp_order(self, symbol: str, side: str, amount: float, price: float, reduce_only: bool = False):
        """
        HyENA 전용 선물 주문 (Builder Code 포함)
        """
        is_buy = (side.upper() == 'BUY')
        
        # 정밀도 처리 (유효숫자 5자리 등 SDK 규칙 준수 필요하지만 여기선 float 처리)
        final_price = float(f"{price:.5g}")
        final_sz = float(f"{amount:.5g}")

        # Limit IOC 주문 (즉시 체결 아니면 취소)
        order_request = {
            "coin": symbol,
            "is_buy": is_buy,
            "sz": final_sz,
            "limit_px": final_price,
            "order_type": {"limit": {"tif": "Ioc"}}, 
            "reduce_only": reduce_only
        }

        try:
            # Builder Code를 포함하여 주문 전송
            res = self.exchange.bulk_orders(
                [order_request], 
                builder={"b": self.builder_address.lower(), "f": self.builder_fee}
            )
            
            if res['status'] == 'ok':
                status = res['response']['data']['statuses'][0]
                if 'filled' in status:
                    fill_info = status['filled']
                    log.info(f"✅ [HyENA] 체결 완료! {symbol} {side} {fill_info['totalSz']} @ {fill_info['avgPx']}")
                    return True
                elif 'error' in status:
                    # 잔고 부족, 가격 괴리 등 주문 거부
                    log.warning(f"⚠️ [HyENA] 주문 거부: {status['error']}")
            else:
                log.error(f"❌ [HyENA] 응답 오류: {res}")
                
        except Exception as e:
            # 상장 전에는 "Coin not found" 에러 발생
            if "Coin not found" not in str(e):
                log.error(f"❌ [HyENA] 주문 예외: {e}")
        return False