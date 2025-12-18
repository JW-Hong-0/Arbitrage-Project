# fetch_exchange_tickers.py
# (⭐️ 2025-11-09: v3 - await 제거 및 close() 제거)

import asyncio
import sys
import pprint
import logging
from decimal import Decimal
import os
import traceback
from typing import List, Dict, Any, Tuple

# --- 1. SDK 임포트 (가장 위로 이동) ---

# 1.1 Hyperliquid (Basedapp) SDK 임포트
try:
    from hyperliquid.info import Info
    from hyperliquid.utils import constants # ⭐️ URL 상수를 가져오기 위해 임포트
except ImportError:
    print("❌ 'hyperliquid' SDK가 설치되지 않았습니다.")
    print("   터미널에 'pip install hyperliquid-python-sdk'를 실행하세요.")
    sys.exit(1)

# 1.2 GRVT SDK 임포트
try:
    from pysdk.grvt_ccxt_pro import GrvtCcxtPro 
    from pysdk.grvt_ccxt_env import GrvtEnv
    from pysdk.grvt_ccxt_logging_selector import logger as grvt_logger
    # from pysdk.grvt_ccxt import GrvtCcxt 
    # from pysdk.grvt_ccxt_env import GrvtEnv
    # from pysdk.grvt_ccxt_logging_selector import logger as grvt_logger
except ImportError:
    print("❌ 'grvt-pysdk'가 설치되지 않았습니다.")
    print("   터미널에 'pip install grvt-pysdk'를 실행하세요.")
    print("--- 오류 상세 ---")
    print(traceback.format_exc()) 
    print("---------------")
    sys.exit(1)

# --- 2. 로컬 설정 임포트 (SDK 임포트 *이후* 실행) ---
try:
    import settings 
except ImportError:
    print("❌ 'settings.py' 파일을 찾을 수 없습니다. 동일한 폴더에 있는지 확인하세요.")
    sys.exit(1)


# --- 3. 로깅 설정 (GRVT 로거 사용) ---
log = grvt_logger
log.setLevel(logging.INFO) 

# --- 4. 거래소별 티커 조회 로직 ---

async def fetch_hyperliquid_tickers(info_api: Info) -> Dict[str, Any]:
    """Hyperliquid (Basedapp)의 모든 perp 마켓 티커와 상세 정보를 조회합니다."""
    try:
        # 1. ⭐️ [핵심 수정] 'await' 키워드 제거
        # info_api.meta()는 더 이상 비동기 함수가 아니므로 await를 사용하지 않습니다.
        meta = info_api.meta()
        universe = meta.get("universe", [])
        
        if not universe:
            log.warning("[Hyperliquid] 'universe' 데이터를 찾을 수 없습니다.")
            return {}

        # 2. 'name', 'szDecimals'만 추출
        tickers_info = {
            asset["name"]: {
                "sz_decimals": asset["szDecimals"]
            }
            for asset in universe
            if asset.get("name") and "szDecimals" in asset
        }
        
        log.info(f"✅ [Hyperliquid] 총 {len(tickers_info)}개 티커 조회 성공")
        return tickers_info
    except Exception as e:
        log.error(f"❌ [Hyperliquid] 티커 조회 실패: {e}")
        log.error(traceback.format_exc())
        return {}

async def fetch_grvt_tickers(grvt_api: GrvtCcxtPro) -> Dict[str, Any]:
    """GRVT의 모든 perp 마켓 티커와 상세 정보를 조회합니다."""
    try:
        # 1. 마켓 메타데이터 로드 (필수)
        log.info("[GRVT] 마켓 메타데이터 로드 중...")
        await grvt_api.load_markets() 
        log.info("✅ [GRVT] 마켓 메타데이터 로드 완료.")

        # 2. 'markets' 속성에서 정보 추출
        markets = grvt_api.markets
        if not markets:
            log.warning("[GRVT] 'markets' 데이터를 찾을 수 없습니다.")
            return {}

        # ⭐️ [디버그 코드 추가] 
        # 67개 markets 중 첫 번째 데이터의 구조를 출력하여 'kind' 키를 확인합니다.
        try:
            first_market_data = list(markets.values())[0]
            log.info(f"[GRVT] [디버그] 'markets' 첫 데이터 샘플: {first_market_data}")
        except Exception as e:
            log.info(f"[GRVT] [디버그] 샘플 데이터 출력 실패: {e}")

        # 3. Perp 마켓('PERPETUAL' 타입)만 필터링
        tickers_info = {}
        for symbol, market_data in markets.items():
            
            # ⭐️ [핵심 수정 1] 
            # 'type' == 'swap' (X) -> 'kind' == 'PERPETUAL' (O)
            if market_data.get('kind') == 'PERPETUAL':
                
                # ⭐️ [핵심 수정 2] SDK의 실제 반환 키('tick_size', 'min_size')로 변경
                tickers_info[symbol] = {
                    "tick_size": market_data.get('tick_size'),       # 가격 정밀도
                    "min_size": market_data.get('min_size'),         # 최소 주문 수량 (수량 정밀도)
                    "base_decimals": market_data.get('base_decimals') # 서명용 10진수
                }

        log.info(f"✅ [GRVT] 총 {len(tickers_info)}개 Perp 티커 조회 성공")
        return tickers_info
    except Exception as e:
        log.error(f"❌ [GRVT] 티커 조회 실패: {e}")
        log.error(traceback.format_exc())
        return {}
    finally:
        # ⭐️ [수정] close() 호출 제거
        log.info("[GRVT] API 객체 사용 완료 (자동 세션 종료).")

def find_common_pairs(hl_tickers: Dict[str, Any], grvt_tickers: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    """ 
    두 거래소의 티커 목록을 비교하여 공통된 페어를 찾습니다.
    (⭐️ 2025-11-09: GRVT 반환 키 구조('tick_size', 'min_size')에 맞게 수정)
    """
    
    common_pairs_for_config = [] # ('BTC', 'BTC_USDT_Perp') 형태
    common_pairs_details = {} # 상세 정보 포함
    
    for grvt_symbol, grvt_info in grvt_tickers.items():
        base_asset = grvt_symbol.split('_')[0]
        
        if base_asset in hl_tickers:
            hl_symbol = base_asset
            hl_info = hl_tickers[hl_symbol]
            
            common_pairs_for_config.append((hl_symbol, grvt_symbol))
            
            common_pairs_details[hl_symbol] = {
                "hyperliquid": {
                    "symbol": hl_symbol,
                    "sz_decimals": hl_info.get("sz_decimals")
                },
                # ⭐️ [핵심 수정] GRVT의 실제 키 이름으로 변경
                "grvt": {
                    "symbol": grvt_symbol,
                    "tick_size": grvt_info.get("tick_size"),
                    "min_size": grvt_info.get("min_size"),
                    "base_decimals": grvt_info.get("base_decimals")
                }
            }
            
    log.info(f"✅ 공통 페어 {len(common_pairs_for_config)}개 발견!")
    return common_pairs_for_config, common_pairs_details

# --- 5. 메인 실행 함수 ---

async def main():
    # .env 파일 로드 (가장 먼저 실행)
    try:
        from dotenv import load_dotenv
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
            log.info(f"✅ '.env' 파일 로드 성공: {dotenv_path}")
        else:
            log.warning(f"⚠️ '.env' 파일을 찾을 수 없습니다: {dotenv_path}. 환경 변수가 이미 설정되었기를 바랍니다.")
    except ImportError:
        log.warning("⚠️ 'python-dotenv'가 설치되지 않았습니다. .env 파일 로드를 건너뜁니다.")


    log.info("--- 1/4 : 🚀 Hyperliquid (Basedapp) 티커 조회 시작 ---")
    
    hl_config = settings.EXCHANGES_CONNECTION.get('hyperliquid', {})
    hl_use_testnet = hl_config.get('USE_TESTNET', False) 
    
    if hl_use_testnet:
        hl_base_url = constants.TESTNET_API_URL
        log.info(f"✅ [Hyperliquid] 테스트넷으로 설정되었습니다. (URL: {hl_base_url})")
    else:
        hl_base_url = constants.MAINNET_API_URL
        log.info(f"✅ [Hyperliquid] 메인넷으로 설정되었습니다. (URL: {hl_base_url})")

    try:
        hl_api = Info(hl_base_url) 
    except Exception as e:
        log.error(f"❌ [Hyperliquid] Info 객체 생성 실패: {e}")
        log.error(traceback.format_exc())
        return 
    
    hl_tickers = await fetch_hyperliquid_tickers(hl_api) 
    log.info("✅ [Hyperliquid] 티커 조회 완료.")


    log.info("\n--- 2/4 : 🚀 GRVT 티커 조회 시작 ---")
    
    grvt_config = settings.EXCHANGES_CONNECTION.get('grvt', {})
    
    # .env 파일에서 키 로드
    grvt_api_key = os.environ.get('GRVT_API_KEY')
    # ⭐️ [핵심] .env의 'GRVT_SECRET_KEY' 변수가 SDK의 'private_key' 매개변수에 해당합니다.
    grvt_private_key = os.environ.get('GRVT_SECRET_KEY') 
    
    grvt_env_str = grvt_config.get('ENVIRONMENT', 'testnet') 
    grvt_use_testnet = (grvt_env_str == 'testnet')
    
    if not grvt_api_key or not grvt_private_key:
        # ⭐️ 변수명 수정
        log.error("❌ '.env' 파일에 'GRVT_API_KEY' 또는 'GRVT_SECRET_KEY'(지갑 개인키)가 없습니다.")
        return

    # ⭐️ [핵심 수정] 
    # GrvtCcxtPro 생성자 시그니처(형식)에 맞게 호출 방식을 변경합니다.
    # 1. 'env' (Enum 객체)를 첫 번째 인자로 분리합니다.
    # 2. 'parameters' (dict)를 세 번째 인자로 분리합니다.
    
    try:
        # 1. GrvtEnv Enum 객체를 준비합니다.
        grvt_env_enum = GrvtEnv.TEST if grvt_use_testnet else GrvtEnv.PROD

        # 2. 'parameters' 딕셔너리를 준비합니다. (grvt_ccxt_base.py 참고)
        grvt_params = {
            'api_key': grvt_api_key,
            'private_key': grvt_private_key # 👈 'secret'이 아닌 'private_key'
            # 'trading_account_id': os.environ.get('GRVT_TRADING_ACCOUNT_ID') # 필요시 추가
        }
        
        # 3. SDK 생성자 형식에 맞게 (env, parameters=...)로 호출합니다.
        grvt_api = GrvtCcxtPro(
            env=grvt_env_enum,       # 👈 1번째 인자 (Enum)
            parameters=grvt_params   # 👈 3번째 인자 (dict)
        )
        
        log.info(f"✅ [GRVT] GrvtCcxtPro 객체 생성 성공. (Env: {grvt_env_enum.value})")

    except Exception as e:
        log.error(f"❌ [GRVT] GrvtCcxtPro 객체 생성 실패: {e}")
        log.error(traceback.format_exc())
        return

    # ⭐️ 이제 이 코드는 'GrvtCcxtPro'의 비동기 함수를 올바르게 호출합니다.
    grvt_tickers = await fetch_grvt_tickers(grvt_api) 

    if not hl_tickers or not grvt_tickers:
        log.error("❌ 한쪽 또는 양쪽 거래소에서 티커를 조회하지 못했습니다. 비교를 중단합니다.")
        return

    log.info("\n--- 3/4 : 🔄 공통 페어 비교 및 상세 정보 출력 ---")
    common_pairs_for_config, common_pairs_details = find_common_pairs(hl_tickers, grvt_tickers)
    
    if common_pairs_details:
        log.info("--- [ 상세 비교 결과 (Pretty Print) ] ---")
        pprint.pprint(common_pairs_details)
        log.info("----------------------------------------")
    else:
        log.warning("⚠️ 공통 페어를 찾지 못했습니다.")

    # 4. 'settings.py'의 'TARGET_PAIRS_CONFIG' 형식으로 출력
    if common_pairs_for_config:
        print("\n--- 4/4 : 💡 [보너스] 공통 페어 'settings.py' 설정 생성 ---")
        
        print("이 내용을 'settings.py'의 'TARGET_PAIRS_CONFIG' 딕셔너리 내부에,")
        print("복사하세요! (기존 항목은 덮어쓰거나 지워주세요)\n")
        
        config_output = "TARGET_PAIRS_CONFIG = {\n"
        
        for hl_symbol, grvt_symbol in common_pairs_for_config:
            
            preset = "major" if hl_symbol in ["BTC", "ETH"] else "alt"
            trade_size_pct = 10.0 
            
            config_output += f'    "{hl_symbol}": {{\n'
            config_output += f'        "symbols": {{\n'
            config_output += f'            "hyperliquid": "{hl_symbol}",\n'
            config_output += f'            "grvt": "{grvt_symbol}"\n'
            config_output += f'        }},\n'
            config_output += f'        "strategy_preset": "{preset}",\n'
            config_output += f'        "trade_size_pct": {trade_size_pct},\n'
            config_output += f'        "trade_size_fixed_usd": None\n'
            config_output += f'    }},\n'
        
        config_output += "}"
        print(config_output)

if __name__ == "__main__":
    # (main 함수 시작 부분으로 .env 로드 로직을 옮겼으므로 여기서는 별도 작업 없음)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("\n🛑 사용자에 의해 프로그램이 중단되었습니다.")
    except Exception as e:
        log.error(f"❌ 메인 실행 중 예상치 못한 오류 발생: {e}")
        log.error(traceback.format_exc())