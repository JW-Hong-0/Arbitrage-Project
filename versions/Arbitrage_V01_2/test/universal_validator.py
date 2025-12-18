# universal_validator.py
# (⭐️ 2025-11-26: v2 - REST API 기반 고속 설정 생성기)

import asyncio
import os
import logging
import sys
from typing import Dict, List
from collections import defaultdict
from dotenv import load_dotenv

# exchange_apis.py
try:
    from exchange_apis import (
        HyperliquidExchange, GrvtExchange, PacificaExchange, 
        VariationalExchange, ExtendedExchange, LighterExchange
    )
except ImportError:
    print("❌ 'exchange_apis.py' 파일이 필요합니다.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("Validator")
load_dotenv()

# 우선순위 설정
PREDEFINED_CONFIGS = {
    "BTC":  {"preset": "major", "size": 50.0},
    "ETH":  {"preset": "major", "size": 50.0},
    "SOL":  {"preset": "alt",   "size": 50.0},
    "BNB":  {"preset": "alt",   "size": 50.0},
    "XRP":  {"preset": "alt",   "size": 30.0},
    "HYPE": {"preset": "pre_market", "size": 30.0},
    "MON":  {"preset": "pre_market", "size": 30.0},
}

class UniversalValidator:
    def __init__(self):
        self.tickers: Dict[str, Dict[str, str]] = defaultdict(dict)

    def normalize_ticker(self, exchange: str, raw_symbol: str) -> str:
        sym = raw_symbol.upper()
        if exchange == 'hyperliquid': return sym
        elif exchange == 'grvt': return sym.split('_')[0]
        elif exchange == 'pacifica': return sym
        elif exchange == 'variational': return sym.split('-')[0]
        elif exchange == 'extended': return sym.split('-')[0]
        elif exchange == 'lighter': return sym.split('_')[0]
        return sym

    async def run(self):
        log.info("🚀 5대 거래소 마켓 데이터 수집 중 (REST API)...")
        
        exchanges = {
            'hyperliquid': HyperliquidExchange(os.getenv("HYPERLIQUID_PRIVATE_KEY", ""), os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS", "")),
            'grvt': GrvtExchange(os.getenv("GRVT_API_KEY", ""), os.getenv("GRVT_SECRET_KEY", ""), os.getenv("GRVT_TRADING_ACCOUNT_ID", "")),
            'pacifica': PacificaExchange(os.getenv("PACIFICA_API_KEY", "")),
            'extended': ExtendedExchange(),
            'lighter': LighterExchange(),
            # 'variational': VariationalExchange(...) # (현재 제외)
        }

        # 1. 병렬 초기화 및 데이터 수집
        tasks = [ex.initialize() for ex in exchanges.values()]
        await asyncio.gather(*tasks)
        
        # 2. 티커 매핑
        for name, ex in exchanges.items():
            symbols = await ex.get_all_symbols()
            log.info(f"   ✅ [{name}] {len(symbols)}개 페어 발견")
            
            for raw_sym in symbols:
                base = self.normalize_ticker(name, raw_sym)
                self.tickers[base][name] = raw_sym
                
        # 3. 설정 파일 생성
        self.generate_config()
        
        # 종료
        for ex in exchanges.values():
            await ex.close()

    def generate_config(self):
        log.info(f"\n📊 총 {len(self.tickers)}개의 고유 티커 처리 중...")
        
        # 정렬 (Predefined -> 알파벳순)
        sorted_keys = sorted(self.tickers.keys(), key=lambda x: (0 if x in PREDEFINED_CONFIGS else 1, x))
        
        output = []
        output.append("# settings.py (부분)")
        output.append("TARGET_PAIRS_CONFIG = {")
        
        for t in sorted_keys:
            ex_map = self.tickers[t]
            
            # 설정값 결정
            if t in PREDEFINED_CONFIGS:
                preset = PREDEFINED_CONFIGS[t]['preset']
                size = PREDEFINED_CONFIGS[t]['size']
            else:
                preset = "volatile" # 기본값
                size = 20.0

            output.append(f'    "{t}": {{')
            output.append(f'        "symbols": {{')
            for ex, sym in ex_map.items():
                output.append(f'            "{ex}": "{sym}",')
            output.append(f'        }},')
            output.append(f'        "strategy_preset": "{preset}",')
            output.append(f'        "trade_size_pct": None,')
            output.append(f'        "trade_size_fixed_usd": {size}')
            output.append(f'    }},')
            
        output.append("}")
        
        with open("generated_settings_v2.py", "w", encoding="utf-8") as f:
            f.write("\n".join(output))
            
        log.info("🎉 'generated_settings_v2.py' 생성 완료!")

if __name__ == "__main__":
    asyncio.run(UniversalValidator().run())