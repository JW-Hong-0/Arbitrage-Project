import asyncio
import requests
import json
import csv
import sys
import os
import logging
import math
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("MarketReport")

# 환경변수 로드
load_dotenv()

# settings.py 및 exchange_apis 로드
try:
    import settings
    from exchange_apis import GrvtExchange
    TARGETS = settings.TARGET_PAIRS_CONFIG
    log.info(f"✅ Settings loaded: Analyzing {len(TARGETS)} target pairs")
except ImportError as e:
    log.error(f"❌ Failed to load modules: {e}")
    sys.exit(1)

class MarketReportGenerator:
    def __init__(self):
        self.data = {
            'hyperliquid': {},
            'pacifica': {},
            'lighter': {},
            'extended': {},
            'grvt': {}
        }

    def fetch_hyperliquid(self):
        print("📡 [1/5] Hyperliquid (Public API)...")
        try:
            res = requests.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}, timeout=5)
            if res.status_code == 200:
                for item in res.json()['universe']:
                    self.data['hyperliquid'][item['name']] = {
                        'min_size': 10 ** (-item['szDecimals']),
                        'qty_prec': item['szDecimals'],
                        'max_lev': item['maxLeverage']
                    }
        except Exception as e: print(f"   ⚠️ HL Failed: {e}")

    def fetch_pacifica(self):
        print("📡 [2/5] Pacifica (Public API)...")
        try:
            res = requests.get("https://api.pacifica.fi/api/v1/info", timeout=5)
            if res.status_code == 200:
                for item in res.json().get('data', []):
                    sym = item['symbol'].upper()
                    lot = float(item.get('lot_size', 0))
                    prec = 0
                    if lot > 0:
                        prec = int(round(-math.log10(lot), 0))
                    
                    self.data['pacifica'][sym] = {
                        'min_size': lot,
                        'qty_prec': prec,
                        'max_lev': item.get('max_leverage')
                    }
        except Exception as e: print(f"   ⚠️ PAC Failed: {e}")

    def fetch_lighter(self):
        print("📡 [3/5] Lighter (Public API)...")
        try:
            res = requests.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBooks", timeout=5)
            if res.status_code == 200:
                for item in res.json().get('order_books', []):
                    m_id = item.get('market_id')
                    sym = item.get('symbol')
                    info = {
                        'min_size': float(item.get('min_base_amount', 0)),
                        'qty_prec': int(item.get('supported_size_decimals', 0)),
                        'price_prec': int(item.get('supported_price_decimals', 0))
                    }
                    self.data['lighter'][m_id] = info
                    self.data['lighter'][sym] = info
        except Exception as e: print(f"   ⚠️ Lighter Failed: {e}")

    def fetch_extended(self):
        print("📡 [4/5] Extended (Public API)...")
        try:
            res = requests.get("https://api.starknet.extended.exchange/api/v1/info/markets", 
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if res.status_code == 200:
                data_list = res.json().get('data', [])
                for item in data_list:
                    name = item.get('name', '')
                    base = item.get('assetName', name.split('-')[0])
                    conf = item.get('tradingConfig', {})
                    self.data['extended'][base] = {
                        'min_size': float(conf.get('minOrderSize', 0)),
                        'qty_prec': int(item.get('assetPrecision', 0)),
                        'max_lev': float(conf.get('maxLeverage', 0))
                    }
        except Exception as e: print(f"   ⚠️ Extended Failed: {e}")

    async def fetch_grvt(self):
        print("📡 [5/5] GRVT (Authenticated SDK)...")
        grvt = None
        try:
            grvt = GrvtExchange()
            if not grvt.grvt:
                print("   ⚠️ GRVT SDK not initialized")
                return

            await grvt.grvt.initialize()
            
            markets = grvt.grvt.markets
            if not markets:
                print("   ⚠️ GRVT Markets is empty!")
                return

            # [디버깅] 실제 데이터 구조 확인용
            first_key = list(markets.keys())[0]
            print(f"   🔍 [DEBUG] RAW Data Sample ({first_key}):")
            print(json.dumps(markets[first_key], default=str, indent=2))

            count = 0
            for symbol, market in markets.items():
                base = symbol.split('_')[0] # BTC_USDT_Perp -> BTC
                
                # 1. 데이터 파싱 (직접 접근 시도)
                # GRVT SDK가 'info'에 넣지 않고 top-level에 두는 경우 대응
                min_sz = market.get('min_size') or market.get('ms')
                if min_sz is None:
                     # info 안에 있을 경우
                     raw = market.get('info', {})
                     min_sz = raw.get('min_size') or raw.get('ms')
                
                # Precision
                prec = market.get('base_decimals') or market.get('bd')
                if prec is None:
                    raw = market.get('info', {})
                    prec = raw.get('base_decimals') or raw.get('bd')

                # 값 변환 (없으면 기본값 대신 '-'로 표시하여 확인)
                final_min_sz = float(min_sz) if min_sz is not None else 0.001
                final_prec = int(prec) if prec is not None else 3
                
                # Leverage (SDK가 불러온 데이터에 max_leverage가 있는지 확인)
                # API 결과(instruments)에는 보통 없으므로 '-'
                # get_all_initial_leverage 호출이 필요하지만 SDK 지원 여부 불투명
                max_lev = market.get('max_leverage') or market.get('ml1') or '-'

                self.data['grvt'][base] = {
                    'min_size': final_min_sz,
                    'qty_prec': final_prec,
                    'max_lev': max_lev
                }
                count += 1

            print(f"   ✅ GRVT Success: Loaded {count} symbols")

        except Exception as e:
            print(f"   ⚠️ GRVT Error: {e}")
        finally:
            # 세션 안전 종료
            if grvt and grvt.grvt and hasattr(grvt.grvt, '_session') and grvt.grvt._session:
                if not grvt.grvt._session.closed:
                    await grvt.grvt._session.close()

    def generate_csv(self):
        print("\n💾 Generating CSV Report...")
        filename = "market_report.csv"
        
        headers = [
            'Ticker', 
            'HL_Min', 'HL_Prec', 'HL_Lev',
            'PAC_Min', 'PAC_Prec', 'PAC_Lev',
            'LTR_Min', 'LTR_Prec',
            'EXT_Min', 'EXT_Prec', 'EXT_Lev',
            'GRVT_Min', 'GRVT_Prec', 'GRVT_Lev'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for ticker, conf in TARGETS.items():
                row = [ticker]
                symbols = conf.get('symbols', {})
                
                # Helper
                def get_col(ex_name, key, default='-'):
                    ex_data = self.data[ex_name]
                    sym = symbols.get(ex_name)
                    
                    if ex_name == 'pacifica' and sym and sym.startswith('k'): sym = sym[1:]
                    if ex_name == 'extended' and sym: sym = sym.split('-')[0]
                    if ex_name == 'grvt' and sym: sym = sym.split('_')[0]
                    
                    target = sym if sym else ticker
                    info = ex_data.get(target, {})
                    return info.get(key, default)

                # HL
                row.extend([get_col('hyperliquid', 'min_size'), get_col('hyperliquid', 'qty_prec'), get_col('hyperliquid', 'max_lev')])
                # PAC
                row.extend([get_col('pacifica', 'min_size'), get_col('pacifica', 'qty_prec'), get_col('pacifica', 'max_lev')])
                # LTR
                ltr_target = symbols.get('lighter')
                ltr_info = self.data['lighter'].get(ltr_target, {})
                row.extend([ltr_info.get('min_size', '-'), ltr_info.get('qty_prec', '-')])
                # EXT
                row.extend([get_col('extended', 'min_size'), get_col('extended', 'qty_prec'), get_col('extended', 'max_lev')])
                # GRVT
                row.extend([get_col('grvt', 'min_size'), get_col('grvt', 'qty_prec'), get_col('grvt', 'max_lev')])
                
                writer.writerow(row)
                
        print(f"✨ Done! '{filename}' created.")

async def main():
    gen = MarketReportGenerator()
    
    gen.fetch_hyperliquid()
    gen.fetch_pacifica()
    gen.fetch_lighter()
    gen.fetch_extended()
    
    await gen.fetch_grvt()
    
    gen.generate_csv()

if __name__ == "__main__":
    asyncio.run(main())