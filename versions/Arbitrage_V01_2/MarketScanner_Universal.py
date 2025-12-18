import asyncio
import aiohttp
import json
import logging
import sys
import ssl
import websockets
import os
import traceback
from collections import defaultdict

# 윈도우 인코딩 호환 설정
sys.stdout.reconfigure(encoding='utf-8')

# 로깅 설정 (지저분한 SDK 로그 차단)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ScannerV10")

# GRVT SDK 등 외부 라이브러리 로그 강제 차단
for lib in ["pysdk", "urllib3", "websockets", "asyncio", "grvt_ccxt", "GrvtCcxtBase"]:
    logging.getLogger(lib).setLevel(logging.CRITICAL)

HEADERS = {"User-Agent": "Mozilla/5.0"}

def print_progress(msg):
    sys.stderr.write(f"\r{msg}")
    sys.stderr.flush()

def normalize_symbol(symbol):
    """티커 표준화 (kPEPE -> PEPE, 1000BONK -> BONK)"""
    if not symbol: return ""
    s = symbol.upper()
    if s.startswith("K") and len(s) > 1 and s[1].isupper(): return s[1:]
    if s.startswith("1000"): return s[4:]
    return s

# =========================================================
# 1. Hyperliquid
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
            raw = asset['name']
            norm = normalize_symbol(raw)
            hl_map[norm] = raw
            
        print_progress(f"🔵 [1/5] Hyperliquid 완료: {len(hl_map)}개 발견      \n")
        return hl_map
    except Exception as e:
        return {}

# =========================================================
# 2. GRVT (수정됨: 에러 핸들링 강화 + 로그 차단)
# =========================================================
def get_grvt_symbols():
    print_progress("⚫ [2/5] GRVT 마켓 리스트 조회 중...")
    try:
        # 환경변수 로드
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("GRVT_API_KEY")
        if not api_key:
            print_progress("⚫ [2/5] GRVT 스킵 (API Key 없음)      \n")
            return {}

        sys.path.append(os.getcwd())
        from pysdk.grvt_ccxt import GrvtCcxt
        from pysdk.grvt_ccxt_env import GrvtEnv

        # SDK 초기화 (로그 없이 조용히)
        grvt = GrvtCcxt(env=GrvtEnv.PROD, parameters={
            'api_key': api_key,
            'private_key': os.getenv("GRVT_SECRET_KEY"),
            'trading_account_id': os.getenv("GRVT_TRADING_ACCOUNT_ID")
        })
        
        # 마켓 조회
        markets = grvt.fetch_markets()
        
        if not markets:
            print_progress("⚫ [2/5] GRVT 데이터 없음 (인증 실패?)      \n")
            return {}
            
        grvt_map = {}
        for m in markets:
            try:
                inst = m.get('instrument', '')
                if inst:
                    # BTC_USDT_Perp -> BTC 추출
                    base = inst.split('_')[0]
                    norm = normalize_symbol(base)
                    grvt_map[norm] = inst
            except:
                continue # 개별 파싱 에러는 무시하고 진행

        print_progress(f"⚫ [2/5] GRVT 완료: {len(grvt_map)}개 확보      \n")
        return grvt_map

    except Exception as e:
        # 에러 발생 시 상세 내용 출력 (디버깅용)
        error_msg = str(e)
        print(f"\n❌ [GRVT Error] {error_msg}")
        # print(traceback.format_exc()) # 필요시 주석 해제
        return {}

# =========================================================
# 3. Pacifica
# =========================================================
async def get_pacifica_symbols():
    print_progress("🟢 [3/5] Pacifica 데이터 수집 중...")
    url = "wss://ws.pacifica.fi/ws"
    pac_map = {}
    
    try:
        async with websockets.connect(url, extra_headers=HEADERS, open_timeout=5) as ws:
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            
            start = asyncio.get_running_loop().time()
            while asyncio.get_running_loop().time() - start < 8:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    if data.get("channel") == "prices":
                        payload = data.get("data", [])
                        if isinstance(payload, list):
                            for item in payload:
                                sym = item.get("symbol")
                                if sym: pac_map[normalize_symbol(sym)] = sym
                            if pac_map: break
                except: continue
                    
        print_progress(f"🟢 [3/5] Pacifica 완료: {len(pac_map)}개 확보      \n")
        return pac_map
    except: return {}

# =========================================================
# 4. Lighter
# =========================================================
async def get_lighter_map():
    print_progress("⚪ [4/5] Lighter ID 조회 중...")
    url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
    ltr_map = {}
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
                                base = sym.split('-')[0]
                                ltr_map[normalize_symbol(base)] = int(mid)
        print_progress(f"⚪ [4/5] Lighter 완료: {len(ltr_map)}개 ID 확보      \n")
        return ltr_map
    except: return {}

# =========================================================
# 5. Extended
# =========================================================
async def check_extended_support(norm_keys):
    print_progress("🟣 [5/5] Extended 연결 검증 시작...")
    ext_map = {}
    url_base = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    targets = list(norm_keys)
    chunk_size = 30
    chunks = [targets[i:i+chunk_size] for i in range(0, len(targets), chunk_size)]
    
    for idx, chunk in enumerate(chunks):
        progress = (idx+1)/len(chunks)*100
        print_progress(f"🟣 [5/5] Extended 검사 중... {progress:.1f}% ({len(ext_map)}개 발견)")
        
        tasks = []
        for norm in chunk:
            tasks.append(_check_ext(norm, url_base, ssl_ctx))
            
        results = await asyncio.gather(*tasks)
        for res in results:
            if res: ext_map[res[0]] = res[1]
            
    print_progress(f"🟣 [5/5] Extended 완료: {len(ext_map)}개 활성 페어      \n")
    return ext_map

async def _check_ext(norm, url_base, ssl_ctx):
    sym = f"{norm}-USD"
    try:
        async with websockets.connect(f"{url_base}/{sym}", ssl=ssl_ctx, open_timeout=1.5) as ws:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
            return (norm, sym)
    except: return None

# =========================================================
# 통합 및 생성
# =========================================================
async def generate():
    hl = get_hyperliquid_symbols()
    grvt = get_grvt_symbols()
    pac = await get_pacifica_symbols()
    ltr = await get_lighter_map()
    
    all_norms = set(hl.keys()) | set(grvt.keys()) | set(pac.keys()) | set(ltr.keys())
    ext = await check_extended_support(all_norms)
    
    print("\n" + "="*60)
    print("TARGET_PAIRS_CONFIG = {")
    
    count = 0
    for norm in sorted(list(all_norms)):
        if norm in ['XAU', 'EUR', 'GBP', 'JPY']: continue

        h_val = f'"{hl[norm]}"' if norm in hl else "None"
        g_val = f'"{grvt[norm]}"' if norm in grvt else "None"
        p_val = f'"{pac[norm]}"' if norm in pac else "None"
        e_val = f'"{ext[norm]}"' if norm in ext else "None"
        l_val = ltr[norm] if norm in ltr else "None"
        
        cnt = 0
        if h_val != "None": cnt += 1
        if g_val != "None": cnt += 1
        if p_val != "None": cnt += 1
        if e_val != "None": cnt += 1
        if l_val != "None": cnt += 1
        
        if cnt >= 2:
            count += 1
            # 키 이름 생성 (HL 우선)
            key_name = hl[norm] if norm in hl else norm
            # k로 시작하면 1000으로 변경
            if key_name.startswith('k') and key_name[1].isupper():
                key_name = "1000" + key_name[1:]
            
            preset = "major" if norm in ['BTC','ETH','SOL','XRP','BNB'] else "volatile"
            size = 50.0 if preset == "major" else 20.0
            
            print(f'    "{key_name}": {{')
            print(f'        "symbols": {{')
            print(f'            "hyperliquid": {h_val},')
            print(f'            "grvt": {g_val},')
            print(f'            "pacifica": {p_val},')
            print(f'            "extended": {e_val},')
            print(f'            "lighter": {l_val},')
            print(f'        }},')
            print(f'        "strategy_preset": "{preset}",')
            print(f'        "trade_size_fixed_usd": {size}')
            print(f'    }},')

    print("}")
    print_progress(f"\n[DONE] {count} clean pairs generated.\n")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(generate())
    except KeyboardInterrupt:
        pass