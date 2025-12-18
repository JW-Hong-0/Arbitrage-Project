import asyncio
import aiohttp
import json
import logging
import sys
import ssl
import websockets
import os
from collections import defaultdict

# 윈도우 인코딩 설정
sys.stdout.reconfigure(encoding='utf-8')

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("Diagnose")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================================================
# 1. Hyperliquid (데이터 기준점)
# =========================================================
def get_hyperliquid_symbols():
    logger.info("[1/4] Hyperliquid 심볼 조회 중...")
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        meta = info.meta()
        
        hl_map = {}
        for asset in meta['universe']:
            raw = asset['name'] # 예: kPEPE
            # k뗀 이름도 매핑 (검색 편의성)
            clean = raw[1:] if raw.startswith('k') else raw
            hl_map[clean] = raw 
            hl_map[raw] = raw
            
        logger.info(f"   => {len(meta['universe'])}개 코인 확보 완료")
        return hl_map
    except Exception as e:
        logger.error(f"   => 실패: {e}")
        return {}

# =========================================================
# 2. Pacifica (정밀 진단 모드)
# =========================================================
async def get_pacifica_symbols_debug():
    logger.info("[2/4] Pacifica 웹소켓 데이터 정밀 분석...")
    url = "wss://ws.pacifica.fi/ws"
    found_symbols = set()
    
    try:
        # 타임아웃 보호를 위한 래퍼
        async with websockets.connect(url, extra_headers=HEADERS, open_timeout=5) as ws:
            logger.info("   => Pacifica 서버 연결 성공. 구독 요청 전송...")
            await ws.send(json.dumps({"method": "subscribe", "params": {"source": "prices"}}))
            
            # 5초간 들어오는 모든 메시지 확인
            start_t = asyncio.get_running_loop().time()
            msg_count = 0
            
            while asyncio.get_running_loop().time() - start_t < 5:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    msg_count += 1
                    data = json.loads(msg)
                    
                    # [디버깅] 첫 번째 메시지 내용 출력 (매우 중요)
                    if msg_count == 1:
                        preview = str(data)[:200]
                        logger.info(f"   => [DEBUG] 첫 수신 데이터: {preview}...")

                    # 데이터 파싱 시도 (다양한 케이스 대응)
                    # Case A: payload 키 안에 딕셔너리 {"BTC": ...}
                    payload = data.get("payload")
                    if isinstance(payload, dict):
                        for t in payload.keys(): found_symbols.add(t)
                    
                    # Case B: 그냥 바로 딕셔너리 {"BTC": ...}
                    elif isinstance(data, dict):
                        for t in data.keys():
                            if t.isupper() and len(t) < 10: # 티커 같은 것만
                                found_symbols.add(t)

                    if found_symbols:
                        logger.info(f"   => 감지됨! {len(found_symbols)}개 티커 발견")
                        break

                except asyncio.TimeoutError:
                    logger.info("   => 데이터 수신 대기중... (Timeout)")
                    continue
                except Exception as e:
                    logger.error(f"   => 파싱 에러: {e}")
                    
    except Exception as e:
        logger.error(f"   => Pacifica 접속 실패: {e}")

    return found_symbols

# =========================================================
# 3. Lighter (REST API)
# =========================================================
async def get_lighter_map():
    logger.info("[3/4] Lighter ID 목록 조회...")
    url = "https://mainnet.zklighter.elliot.ai/api/v1/orderBooks"
    mapping = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # API 구조 유연하게 처리
                    if "order_books" in data:
                        items = data["order_books"]
                    elif isinstance(data, list):
                        items = data
                    else:
                        items = []

                    for item in items:
                        sym = item.get('symbol')
                        mid = item.get('market_id')
                        if sym:
                            short = sym.split('-')[0]
                            mapping[short] = int(mid)
                            # k 제거 버전 등 추가 매핑
                            if "1000" in short:
                                mapping[short.replace("1000", "")] = int(mid)
        logger.info(f"   => {len(mapping)}개 ID 확보")
    except:
        logger.warning("   => Lighter 조회 실패 (Skip)")
    return mapping

# =========================================================
# 4. Extended (배치 처리 + 진행률 표시)
# =========================================================
async def check_extended_support_batch(target_coins):
    logger.info("[4/4] Extended 지원 여부 전수 조사 (배치 모드)...")
    valid_symbols = set()
    url_base = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1/orderbooks"
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    # 20개씩 끊어서 처리
    chunk_size = 20
    chunks = [target_coins[i:i + chunk_size] for i in range(0, len(target_coins), chunk_size)]
    
    total_chunks = len(chunks)
    
    for idx, chunk in enumerate(chunks):
        # 진행률 표시 (사용자가 멈췄다고 생각하지 않게)
        print(f"   ... 진행 중: Batch {idx+1}/{total_chunks} ({len(valid_symbols)}개 발견)", end='\r')
        
        tasks = []
        for coin in chunk:
            tasks.append(_check_single_extended(coin, url_base, ssl_ctx))
        
        results = await asyncio.gather(*tasks)
        for res in results:
            if res: valid_symbols.add(res)
            
    print(f"\n   => 완료! {len(valid_symbols)}개 Extended 페어 확인됨")
    return valid_symbols

async def _check_single_extended(coin, url_base, ssl_ctx):
    # 티커 명명 규칙 추측: BTC-USD
    sym = f"{coin}-USD"
    url = f"{url_base}/{sym}"
    try:
        # 타임아웃을 1초로 매우 짧게 설정하여 속도 향상
        async with websockets.connect(url, ssl=ssl_ctx, open_timeout=1.0) as ws:
            # 데이터 오면 성공
            await asyncio.wait_for(ws.recv(), timeout=1.0)
            return sym
    except:
        return None

# =========================================================
# 최종 생성기
# =========================================================
async def generate_final_settings():
    print("\n" + "="*60)
    print(" 🛠️ Arbitrage Bot Settings Generator (Diagnose Mode)")
    print("="*60 + "\n")
    
    # 1. 데이터 수집
    hl_data = get_hyperliquid_symbols()
    
    # HL 데이터가 없으면 진행 불가
    if not hl_data:
        print("❌ 치명적 오류: Hyperliquid 심볼을 가져오지 못했습니다. 인터넷 연결을 확인하세요.")
        return

    pac_data = await get_pacifica_symbols_debug()
    ltr_data = await get_lighter_map()
    
    # Extended 검사 대상: HL에 있는 심볼들 (k 제거한 버전으로)
    ext_check_candidates = []
    for k in hl_data.keys():
        if k.startswith('k'): ext_check_candidates.append(k[1:])
        elif k.startswith('1000'): ext_check_candidates.append(k.replace('1000', ''))
        else: ext_check_candidates.append(k)
    
    ext_data = await check_extended_support_batch(list(set(ext_check_candidates)))
    
    # 2. 파일 작성
    print("\n" + "="*60)
    print("# 아래 내용을 settings.py에 덮어쓰세요 (복사 시작)")
    print("="*60)
    print("TARGET_PAIRS_CONFIG = {")
    
    processed = set()
    # 정렬하여 출력
    sorted_keys = sorted([k for k in hl_data.keys() if not k.startswith('k') and not k.startswith('1000')]) # 깔끔한 키 위주
    
    count = 0
    for key in sorted_keys:
        hl_symbol = hl_data[key]
        
        # 중복 처리
        if hl_symbol in processed: continue
        
        # 1. Pacifica 매칭 (키, HL심볼, k제거, 1000제거 다 확인)
        pac_val = "None"
        candidates = [key, hl_symbol, key.replace('k',''), key.replace('1000','')]
        for c in candidates:
            if c in pac_data:
                pac_val = f'"{c}"'
                break
        
        # 2. Lighter 매칭
        ltr_val = "None"
        for c in candidates:
            if c in ltr_data:
                ltr_val = ltr_data[c]
                break
        
        # 3. Extended 매칭
        ext_val = "None"
        for c in candidates:
            target = f"{c}-USD"
            if target in ext_data:
                ext_val = f'"{target}"'
                break
        
        # 4. GRVT 매칭 (HL 심볼 기반 추정)
        grvt_val = f'"{hl_symbol}_USDT_Perp"'
        
        # 필터링: HL 포함 2곳 이상이면 등록 (GRVT는 있다고 가정하므로 사실상 모두 등록됨)
        # 하지만 너무 많은 잡코인을 거르기 위해, GRVT 외에 하나라도 더 있는 놈들을 우선할 수 있음.
        # 사용자 요청: "데이터가 쏟아져 나오게" -> 전부 다 등록.
        
        processed.add(hl_symbol)
        count += 1
        
        # 메이저 코인 판별
        is_major = key in ['BTC', 'ETH', 'SOL', 'XRP', 'BNB', 'DOGE', 'AVAX', 'SUI', 'ARB']
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
    print(f"\n# [완료] 총 {count}개의 페어 설정이 생성되었습니다.")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(generate_final_settings())