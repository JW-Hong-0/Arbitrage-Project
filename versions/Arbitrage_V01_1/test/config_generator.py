# config_generator.py
# (⭐️ 2025-11-26: v2 - 5대 거래소 정밀 진단 및 설정 생성)

import asyncio
import os
import logging
from typing import Dict, List
from dotenv import load_dotenv

# exchange_apis.py에서 거래소 클래스 임포트
try:
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange, 
        VariationalExchange, ExtendedExchange, LighterExchange
    )
except ImportError:
    print("❌ 'exchange_apis.py' 파일이 필요합니다.")
    exit(1)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("ConfigGen")

load_dotenv()

PREDEFINED_CONFIGS = {
    "BTC":  {"preset": "major", "size": 50.0},
    "ETH":  {"preset": "major", "size": 50.0},
    "SOL":  {"preset": "alt",   "size": 50.0},
    "BNB":  {"preset": "alt",   "size": 50.0},
    "HYPE": {"preset": "alt",   "size": 50.0},
    "XPL":  {"preset": "alt",   "size": 30.0},
    "XRP":  {"preset": "alt",   "size": 30.0},
    "ADA":  {"preset": "alt",   "size": 30.0},
    "WLD":  {"preset": "alt",   "size": 30.0},
    "WLFI": {"preset": "alt",   "size": 30.0},
}
DEFAULT_PRESET = "volatile"
DEFAULT_SIZE = 20.0

def normalize_ticker(exchange: str, raw_symbol: str) -> str:
    sym = raw_symbol.upper()
    if exchange == 'hyperliquid': return sym
    elif exchange == 'grvt': return sym.split('_')[0]
    elif exchange == 'pacifica': return sym
    elif exchange == 'variational': return sym.split('-')[0]
    elif exchange == 'extended': return sym.split('-')[0]
    elif exchange == 'lighter': return sym.split('_')[0]
    return sym

async def main():
    log.info("🚀 [정밀 진단] 5개 거래소 데이터 수집 시작...")

    exchanges = {
        'hyperliquid': HyperliquidExchange(os.getenv("HYPERLIQUID_PRIVATE_KEY", ""), os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS", "")),
        'grvt': GrvtExchange(os.getenv("GRVT_API_KEY", ""), os.getenv("GRVT_SECRET_KEY", ""), os.getenv("GRVT_TRADING_ACCOUNT_ID", "")),
        'pacifica': PacificaExchange(os.getenv("PACIFICA_API_KEY", "")),
        'variational': VariationalExchange(os.getenv("VARIATIONAL_KEY", ""), os.getenv("VARIATIONAL_SECRET", "")),
        'extended': ExtendedExchange(),
        'lighter': LighterExchange()
    }

    # 1. 데이터 수집 (병렬)
    results = {}
    for name, ex in exchanges.items():
        log.info(f"📡 [{name}] 연결 시도...")
        if await ex.initialize():
            symbols = await ex.get_all_symbols()
            funding_rates = await ex.fetch_funding_rates()
            
            # 진단 리포트 출력
            log.info(f"✅ [{name}] 연결 성공")
            log.info(f"   - 발견된 심볼: {len(symbols)}개")
            log.info(f"   - 펀딩비 데이터: {'✅ 수신' if funding_rates else '⚠️ 미수신 (API 확인 필요)'}")
            
            # 샘플 데이터 검증 (BTC 등)
            sample_ticker = next((s for s in symbols if 'BTC' in s), None)
            if sample_ticker:
                lev = ex.get_max_leverage(sample_ticker)
                log.info(f"   - [샘플] {sample_ticker}: Max Lev {lev}x")
            else:
                log.warning(f"   - [주의] BTC 심볼을 찾을 수 없음")

            results[name] = symbols
        else:
            log.error(f"❌ [{name}] 초기화 실패. (API 키 또는 네트워크 확인)")

    # 2. 데이터 통합
    merged_map = {}
    for ex_name, symbols in results.items():
        for raw_sym in symbols:
            base_ticker = normalize_ticker(ex_name, raw_sym)
            if base_ticker not in merged_map: merged_map[base_ticker] = {}
            merged_map[base_ticker][ex_name] = raw_sym

    # 3. 설정 파일 생성
    log.info(f"📊 총 {len(merged_map)}개의 고유 티커(Pair) 처리 중...")
    sorted_tickers = sorted(merged_map.keys(), key=lambda x: (0 if x in PREDEFINED_CONFIGS else 1, x))
    
    output_lines = []
    output_lines.append("# === 2. 거래 대상 페어 (자동 생성됨) ===")
    output_lines.append("TARGET_PAIRS_CONFIG = {")

    for ticker in sorted_tickers:
        exchange_map = merged_map[ticker]
        # 최소 2개 이상 거래소에 상장된 것만 필터링 (선택사항)
        # if len(exchange_map) < 2: continue 

        if ticker in PREDEFINED_CONFIGS:
            preset = PREDEFINED_CONFIGS[ticker]['preset']
            size = PREDEFINED_CONFIGS[ticker]['size']
            comment = "  # [고정 설정]"
        else:
            preset = DEFAULT_PRESET
            size = DEFAULT_SIZE
            comment = ""

        output_lines.append(f'    "{ticker}": {{')
        output_lines.append(f'        "symbols": {{')
        for ex_name, sym in exchange_map.items():
            output_lines.append(f'            "{ex_name}": "{sym}",')
        output_lines.append(f'        }},')
        output_lines.append(f'        "strategy_preset": "{preset}",{comment}')
        output_lines.append(f'        "trade_size_pct": None,')
        output_lines.append(f'        "trade_size_fixed_usd": {size}')
        output_lines.append(f'    }},')

    output_lines.append("}")

    with open("generated_settings.py", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
        
    log.info("🎉 'generated_settings.py' 생성 완료!")
    
    # 종료
    for ex in exchanges.values():
        await ex.close()

if __name__ == "__main__":
    asyncio.run(main())