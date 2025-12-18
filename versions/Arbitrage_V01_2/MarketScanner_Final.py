import asyncio
import aiohttp
import json
import logging
import sys
import ssl
import websockets
from collections import defaultdict

# 윈도우 인코딩 호환 설정
sys.stdout.reconfigure(encoding='utf-8')

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ScannerV9")

HEADERS = {"User-Agent": "Mozilla/5.0"}

def print_progress(msg):
    sys.stderr.write(f"\r{msg}")
    sys.stderr.flush()

# =========================================================
# 1. Hyperliquid (데이터 기준점)
# =========================================================
def get_hyperliquid_symbols():
    print_progress("🔵 [1/5] Hyperliquid 데이터 수집 중...")
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        meta = info.meta()
        
        hl_map = {}
        for asset in meta['universe']:
            raw = asset['name'] # 예: kPEPE
            
            # Key 이름 생성 (kPEPE -> 1000PEPE)
            if raw.startswith('k') and raw[1].isupper():
                key_name = "1000" + raw[1:]
            else:
                key_name = raw
                
            hl_map[key_name] = raw
            
        print_progress(f"🔵 [1/5] Hyperliquid 완료: {len(hl_map)}개 발견      \n")
        return hl_map
    except Exception as e:
        logger.error(f"\n[ERROR] Hyperliquid Scan Failed: {e}")
        return {}

# =========================================================
# 2. Pacifica (안전장치 강화)
# =========================================================
async def get_pacifica_symbols():
    print_progress("🟢 [2/5] Pacifica 데이터 수집 중...")
    url = "wss://ws.pacifica.fi/ws"
    found_symbols = set()
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, open_timeout=5) as ws:
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            
            start_time = asyncio.get_running_loop().time()
            while asyncio.get_running_loop().time() - start_time < 8:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    
                    if data.get("channel") == "prices":
                        payload = data.get("data", [])
                        if isinstance(payload, list):
                            for item in payload:
                                sym = item.get("symbol")
                                if sym: found_symbols.add(sym)
                            if found_symbols: break
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
                    
        print_progress(f"🟢 [2/5] Pacifica 완료: {len(found_symbols)}개 확보      \n")
        return found_symbols
    except Exception as e:
        print_progress(f"🟢 [2/5] Pacifica 건너뜀 (연결 실패)      \n")
        return set()

# =========================================================
# 3. Lighter (REST API)
# =========================================================
async def get_lighter_map():
    print_progress("⚪ [3/5] Lighter ID 매핑 조회 중...")
    url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
    mapping = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("order_books", []) if "order_books" in data else data
                    if isinstance(items, list):
                        for item in items:
                            sym = item.get('symbol')
                            mid = item.get('market_id')
                            if sym:
                                short = sym.split('-')[0]
                                mapping[short] = int(mid)
                                if "1000" in short:
                                    mapping[short.replace("1000", "")] = int(mid)
                                    
        print_progress(f"⚪ [3/5] Lighter 완료: {len(mapping)}개 ID 확보      \n")
        return mapping
    except Exception as e:
        print_progress(f"⚪ [3/5] Lighter 건너뜀 (API 실패)      \n")
        return {}

# =========================================================
# 4. Extended (배치 처리)
# =========================================================
async def check_extended_support(target_coins):
    print_progress("🟣 [4/5] Extended 연결 검증 시작...")
    valid_symbols = set()
    url_base = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    targets = list(set(target_coins))
    chunk_size = 30
    chunks = [targets[i:i + chunk_size] for i in range(0, len(targets), chunk_size)]
    
    for idx, chunk in enumerate(chunks):
        progress = (idx + 1) / len(chunks) * 100
        print_progress(f"🟣 [4/5] Extended 검사 중... {progress:.1f}% ({len(valid_symbols)}개 발견)")
        
        tasks = []
        for coin in chunk:
            tasks.append(_check_single_extended(coin, url_base, ssl_ctx))
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, str): valid_symbols.add(res)
        except:
            pass
            
    print_progress(f"🟣 [4/5] Extended 완료: {len(valid_symbols)}개 활성 페어 확인      \n")
    return valid_symbols

async def _check_single_extended(coin, url_base, ssl_ctx):
    clean_coin = coin.replace("1000", "").replace("k", "") if coin.startswith("k") or coin.startswith("1000") else coin
    sym = f"{clean_coin}-USD"
    url = f"{url_base}/{sym}"
    try:
        async with websockets.connect(url, ssl=ssl_ctx, open_timeout=1.5) as ws:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
            return sym
    except:
        return None

# =========================================================
# 5. GRVT (설정 생성)
# =========================================================
def check_grvt_support():
    print_progress("⚫ [5/5] GRVT 설정 생성 중...")
    print_progress("⚫ [5/5] GRVT 완료: Hyperliquid 매핑 적용      \n")
    return True

# =========================================================
# 메인 생성기
# =========================================================
async def generate_final_settings():
    hl_map = get_hyperliquid_symbols()
    
    pac_data = set()
    try: pac_data = await get_pacifica_symbols()
    except: pass
    
    ltr_data = {}
    try: ltr_data = await get_lighter_map()
    except: pass
    
    check_list = []
    for k, v in hl_map.items():
        check_list.append(k)
        check_list.append(v)
        if "1000" in k: check_list.append(k.replace("1000", ""))
        
    ext_data = set()
    try: ext_data = await check_extended_support(check_list)
    except: pass
    
    check_grvt_support()
    
    print("\n" + "="*60)
    print("TARGET_PAIRS_CONFIG = {")
    
    count = 0
    processed = set()
    sorted_keys = sorted(hl_map.keys())
    
    for key in sorted_keys:
        hl_symbol = hl_map[key]
        if hl_symbol in processed: continue
        
        # 1. Pacifica
        pac_val = "None"
        search_keys = [key, hl_symbol, key.replace("1000", ""), hl_symbol.replace("k", "")]
        for s in search_keys:
            if s in pac_data:
                pac_val = f'"{s}"'
                break
        
        # 2. Lighter
        ltr_val = "None"
        for s in search_keys:
            if s in ltr_data:
                ltr_val = ltr_data[s]
                break
                
        # 3. Extended
        ext_val = "None"
        for s in search_keys:
            t = f"{s}-USD"
            if t in ext_data:
                ext_val = f'"{t}"'
                break
                
        # 4. GRVT (수정됨: _USDT_Perp 접미사 부활)
        # kBONK -> kBONK_USDT_Perp
        grvt_val = f'"{hl_symbol}_USDT_Perp"' 
        
        # 필터링
        support_cnt = 1 # HL
        if pac_val != "None": support_cnt += 1
        if ltr_val != "None": support_cnt += 1
        if ext_val != "None": support_cnt += 1
        support_cnt += 1 # GRVT
        
        if support_cnt >= 2:
            processed.add(hl_symbol)
            count += 1
            
            is_major = key in ['BTC','ETH','SOL','XRP','BNB','DOGE','AVAX','SUI','ARB']
            preset = "major" if is_major else "volatile"
            size = 50.0 if is_major else 20.0
            
            print(f'    "{key}": {{')
            print(f'        "symbols": {{')
            print(f'            "hyperliquid": "{hl_symbol}",')
            print(f'            "grvt": {grvt_val},')
            print(f'            "pacifica": {pac_val},')
            print(f'            "extended": {ext_val},')
            print(f'            "lighter": {ltr_val},')
            print(f'        }},')
            print(f'        "strategy_preset": "{preset}",')
            print(f'        "trade_size_fixed_usd": {size}')
            print(f'    }},')

    print("}")
    print_progress(f"\n[DONE] {count} pairs generated.\n")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(generate_final_settings())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Critical Error: {e}")