import json
from hyperliquid.info import Info

def find_hyena():
    print("🔍 Hyperliquid HIP-3 DEX 목록 검색 시작...")
    try:
        # 웹소켓 없이 정보 조회
        info = Info(skip_ws=True)
        
        # 전체 DEX 목록 가져오기
        dexs = info.perp_dexs()
        
        print(f"📋 총 {len(dexs)}개의 DEX 항목 수신됨.")
        
        hyena_found = False
        
        # 목록 순회 (None 체크 추가)
        for i, dex in enumerate(dexs):
            if dex is None:
                print(f"  [Index {i}] Mainnet (Skipping...)")
                continue
                
            # DEX 정보 출력
            dex_name = dex.get('name', 'Unknown')
            dex_builder = dex.get('builder', 'Unknown')
            
            print(f"  [Index {i}] Name: {dex_name} | Builder: {dex_builder}")
            
            # 'HyENA' 또는 'Hyperunit' 등 관련 키워드 찾기
            # HyENA의 공식 명칭이 다를 수 있으므로 'HyENA' 포함 여부 확인
            if "HyENA" in dex_name or "hyena" in dex_name.lower() or "Hyperunit" in dex_name: # 예시 키워드 추가
                print(f"\n✅ [HyENA DEX 발견!]")
                print(f"   ▶ DEX ID (Name): {dex_name}")  # 이 값을 설정에 사용해야 함
                print(f"   ▶ Dex Index: {i}")
                print(f"   ▶ Builder: {dex_builder}")
                hyena_found = True
                
                # 상세 마켓 데이터 조회 시도
                print("\n   [마켓 세부 정보 조회]")
                try:
                    # DEX Name을 ID로 사용하여 메타데이터 조회
                    meta = info.meta(dex=dex_name)
                    for asset in meta['universe']:
                        print(f"     • {asset['name']}: Decimals={asset['szDecimals']}, MaxLev={asset['maxLeverage']}")
                except Exception as e:
                    print(f"     ❌ 메타데이터 조회 실패: {e}")
                
                # 하나 찾으면 종료 (원하면 break 제거)
                break
                
        if not hyena_found:
            print("\n⚠️ 'HyENA' 이름의 DEX를 찾지 못했습니다. 위 목록에서 직접 이름을 확인하세요.")
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_hyena()