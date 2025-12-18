import time
import uuid
import requests
import logging
import json
import base58
import asyncio
import websockets
from typing import Dict, Optional, Any, List
from solders.keypair import Keypair

# 로깅 설정
log = logging.getLogger("PacificaTrader")
log.setLevel(logging.INFO)

# 기본 API URL
REST_URL = "https://api.pacifica.fi/api/v1"
WS_URL = "wss://ws.pacifica.fi/ws"

# --- 기본 티커 설정 ---
DEFAULT_PACIFICA_CONFIG = {
    "BTC": {"symbol": "BTC", "price_precision": 1, "qty_precision": 3, "min_qty": 0.001},
    "ETH": {"symbol": "ETH", "price_precision": 2, "qty_precision": 3, "min_qty": 0.01},
    "SOL": {"symbol": "SOL", "price_precision": 3, "qty_precision": 2, "min_qty": 0.1},
}

# --- 헬퍼 함수 ---
def sort_json_keys(value):
    if isinstance(value, dict):
        return {k: sort_json_keys(value[k]) for k in sorted(value.keys())}
    elif isinstance(value, list):
        return [sort_json_keys(item) for item in value]
    else:
        return value

def prepare_message(header, payload):
    if "type" not in header or "timestamp" not in header or "expiry_window" not in header:
        raise ValueError("Header must have type, timestamp, and expiry_window")
    data = {**header, "data": payload}
    sorted_data = sort_json_keys(data)
    return json.dumps(sorted_data, separators=(",", ":"))

def sign_message(header, payload, keypair):
    message = prepare_message(header, payload)
    message_bytes = message.encode("utf-8")
    signature = keypair.sign_message(message_bytes)
    return (message, base58.b58encode(bytes(signature)).decode("ascii"))


class PacificaTrader:
    def __init__(self, main_address: str, agent_private_key: str):
        self.main_address = main_address
        self.agent_private_key = agent_private_key
        self.market_config = DEFAULT_PACIFICA_CONFIG.copy()

        if not self.main_address or not self.agent_private_key:
            raise ValueError("메인 주소 또는 에이전트 키가 설정되지 않았습니다.")

        try:
            self.agent_keypair = Keypair.from_base58_string(self.agent_private_key)
            self.agent_public_key = str(self.agent_keypair.pubkey())
            
            log.info(f"[Pacifica] 초기화 완료.")
            log.info(f"   - Main Account: {self.main_address}")
            log.info(f"   - Agent Wallet: {self.agent_public_key}")
            
            self.fetch_exchange_config()
            
        except Exception as e:
            log.error(f"[Pacifica] Agent Keypair 생성 실패: {e}")
            raise

    def _get_headers(self):
        return {"Content-Type": "application/json"}

    async def _fetch_price_async(self, ticker: str, timeout: int = 10) -> float:
        target_symbol = ticker.upper()
        try:
            async with websockets.connect(WS_URL, ping_interval=None) as ws:
                await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        data = json.loads(msg)
                        if data.get("channel") == "prices":
                            items = data.get("data", [])
                            if isinstance(items, dict): items = [items]
                            for item in items:
                                raw_sym = item.get("symbol", "").upper()
                                if raw_sym == target_symbol or \
                                   raw_sym == f"k{target_symbol}" or \
                                   (raw_sym.startswith('k') and raw_sym[1:] == target_symbol):
                                    price = float(item.get("mark") or item.get("oracle") or 0)
                                    if price > 0: return price
                    except asyncio.TimeoutError: continue
                    except Exception: continue
        except Exception as e:
            log.error(f"[WS] 가격 조회 실패: {e}")
        return 0.0

    def get_current_price(self, ticker: str) -> float:
        try:
            try: loop = asyncio.get_event_loop()
            except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            if loop.is_running(): return 0.0 
            return loop.run_until_complete(self._fetch_price_async(ticker))
        except Exception as e:
            log.error(f"[Price] 가격 조회 에러: {e}")
            return 0.0

    def fetch_exchange_config(self):
        try:
            url = f"{REST_URL}/info" 
            requests.get(url, headers=self._get_headers(), timeout=3)
        except Exception: pass

    def _create_signature(self, req_type: str, payload: Dict):
        timestamp = int(time.time() * 1000)
        expiry_window = 5000 
        signature_header = {"timestamp": timestamp, "expiry_window": expiry_window, "type": req_type}
        message, signature = sign_message(signature_header, payload, self.agent_keypair)
        request_header = {
            "account": self.main_address, "agent_wallet": self.agent_public_key, 
            "signature": signature, "timestamp": timestamp, "expiry_window": expiry_window,
        }
        return request_header, message

    def get_account_info(self) -> Dict:
        """기본 계정 정보 (잔고용)"""
        try:
            url = f"{REST_URL}/account?account={self.main_address}"
            response = requests.get(url, headers=self._get_headers())
            return response.json() if response.status_code == 200 else {}
        except Exception as e:
            log.error(f"[Pacifica] 계정 조회 에러: {e}")
            return {}

    def get_balances(self) -> float:
        response = self.get_account_info()
        try:
            data = response.get('data', {})
            if 'available_to_spend' in data: return float(data['available_to_spend'])
            if 'account_equity' in data: return float(data['account_equity'])
        except Exception: pass
        return 0.0

    # [중요 수정] 포지션 전용 엔드포인트 사용 (/positions)
    def get_open_positions_raw(self) -> Dict:
        """
        API 문서 기반: GET /api/v1/positions?account=...
        """
        try:
            url = f"{REST_URL}/positions"
            params = {"account": self.main_address}
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"❌ [Pacifica] 포지션 조회 실패 (Status: {response.status_code}): {response.text}")
                return {}
        except Exception as e:
            log.error(f"❌ [Pacifica] 포지션 요청 중 예외: {e}")
            return {}

    # [신규 추가] 트레이드 히스토리 조회 (/trades/history)
    def get_trade_history(self, symbol: str = None, limit: int = 5) -> Dict:
        """
        API 문서 기반: GET /api/v1/trades/history
        """
        try:
            url = f"{REST_URL}/trades/history"
            params = {
                "account": self.main_address,
                "limit": limit
            }
            if symbol:
                params["symbol"] = symbol
                
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"❌ [Pacifica] 거래내역 조회 실패: {response.text}")
                return {}
        except Exception as e:
            log.error(f"❌ [Pacifica] 거래내역 요청 예외: {e}")
            return {}

    def get_positions(self) -> Dict[str, Dict]:
        """
        [수정됨] /positions 엔드포인트를 사용하여 포지션 파싱
        """
        response = self.get_open_positions_raw()
        positions = {}
        
        try:
            # 응답 구조: {'success': True, 'data': [...]}
            data_list = response.get('data', [])
            if not isinstance(data_list, list):
                log.warning(f"⚠️ 포지션 데이터가 리스트가 아님: {data_list}")
                return {}

            for p in data_list:
                raw_sym = p.get('symbol', '').upper()
                # amount는 문자열로 옴 ("223.72")
                size_str = p.get('amount', '0')
                size = float(size_str)
                side_raw = p.get('side', '').lower()  # "ask" or "bid" (or "long"/"short"?)
                
                # side 변환
                if side_raw in ['bid', 'buy', 'long']:
                    side = 'LONG'
                elif side_raw in ['ask', 'sell', 'short']:
                    side = 'SHORT'
                else:
                    side = side_raw.upper()

                if size != 0:
                    norm_sym = raw_sym # 심볼 매핑 필요시 여기서 처리
                    positions[norm_sym] = {
                        'symbol': norm_sym,
                        'amount': abs(size),
                        'side': side,
                        'entry_price': float(p.get('entry_price', 0)),
                        'unrealized_pnl': 0.0 # /positions 엔드포인트에 pnl 필드가 없을 수 있음
                    }
        except Exception as e:
            log.error(f"[Pacifica] 포지션 파싱 에러: {e}")
            
        return positions

    def place_market_order(self, ticker: str, side: str, amount: float, reduce_only: bool = False):
        config = self.market_config.get(ticker)
        if not config:
            log.error(f"[Pacifica] 설정되지 않은 티커: {ticker}")
            return None
        
        order_side = "bid" if side.upper() == "BUY" else "ask"
        qty_precision = config.get('qty_precision', 3)
        fmt_amount = f"{amount:.{qty_precision}f}"
        
        payload = {
            "symbol": config['symbol'],
            "reduce_only": reduce_only,
            "amount": fmt_amount,
            "side": order_side,
            "slippage_percent": "0.5",
            "client_order_id": str(uuid.uuid4())
        }

        req_header, _ = self._create_signature("create_market_order", payload)
        request_body = {**req_header, **payload}
        url = f"{REST_URL}/orders/create_market"
        
        try:
            response = requests.post(url, json=request_body, headers=self._get_headers())
            try: res_json = response.json()
            except: return None

            if response.status_code == 200 and res_json.get('success') is True:
                log.info(f"🚀 [Pacifica] 주문 성공: {ticker} {side} {fmt_amount}")
                return res_json
            else:
                log.error(f"❌ [Pacifica] 주문 실패: {res_json}")
                return None
        except Exception as e:
            log.error(f"❌ [Pacifica] 예외 발생: {e}")
            return None

    def cancel_order(self, order_id_or_client_id):
        payload = {
            "order_id": order_id_or_client_id if isinstance(order_id_or_client_id, int) else None,
            "client_order_id": order_id_or_client_id if isinstance(order_id_or_client_id, str) else None
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        req_header, _ = self._create_signature("cancel_order", payload)
        request_body = {**req_header, **payload}
        url = f"{REST_URL}/orders/cancel"
        response = requests.post(url, json=request_body, headers=self._get_headers())
        return response.json()