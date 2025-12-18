# settings.py
# (⭐️ 최종 버전: 다중 거래소 매핑, 전략 그룹화, %/고정 금액 동시 지원)
#cd /d D:\Program_Files\Crypto\HyperLiquid\Arbitrage_V01_2
#python arbitrage_bot.py
#python run_ui.py
#python gui_dashboard_V5.py
# settings.py
# (⭐️ 2025-11-26: v60 - 5대 거래소 지원 및 고변동성 방어 전략 추가)

import os
from dotenv import load_dotenv

# .env 파일 로드
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# === 1. 시뮬레이션 및 자산 설정 ===
SIMULATION_CONFIG = {
    # 초기 잔고 (가상)
    'INITIAL_BALANCES': {
        'hyperliquid': 200.0,
        'grvt': 200.0,
        'pacifica': 200.0,
        'extended': 200.0,
        'lighter': 200.0
    },
    
    # [중요 수정] 수수료율 (Decimal 단위: 0.01% -> 0.0001)
    # 예: 0.045% -> 0.00045
    'FEES': {
        'hyperliquid': 0.000432, # 0.0432%
        'grvt': 0.00045,         # 0.045%
        'pacifica': 0.0006,      # 0.06%
        'extended': 0.00025,     # 0.025%
        'lighter': 0.0           # 0.0%
    },
    
    'VIRTUAL_LEVERAGE': 3.0,
    'HEALTH_CHECK_INTERVAL_SEC': 10 
}

# 포지션 관리 설정
POSITION_MAX_HOLD_SECONDS = 7200  # 1시간 뒤 강제 청산
POSITION_MIN_HOLD_SECONDS = 300    # 최소 1분 보유 (노이즈 방어)
PACIFICA_VIRTUAL_SPREAD = 0.0001
# === 2. 전략 프리셋 (Strategy Presets) ===
STRATEGY_PRESETS = {
    "major": { 
        "entry_threshold_pct": 0.1,  # 메이저 코인은 0.1%도 큼. 0.2%로 상향 추천
        "exit_threshold_pct": 0.02 
    },
    "alt": { 
        "entry_threshold_pct": 0.2,  # 0.3 -> 0.4 상향 추천
        "exit_threshold_pct": 0.05 
    },
    "volatile": { 
        "entry_threshold_pct": 0.5,  # 사용자님 제안 (Good!)
        "exit_threshold_pct": 0.1 
    },
    "pre_market": { 
        "entry_threshold_pct": 15.0, 
        "exit_threshold_pct": 1.0 
    }
}

BASED_APP_CONFIG = {
    "ENABLED": True,
    "BUILDER_ADDRESS": "0x1924b8561eeF20e70Ede628A296175D358BE80e5",
    "BUILDER_FEE": 25,  # 0.025% -> 25 (Hyperliquid 포맷은 정수형 sdk 확인 필요, 보통 0.025%는 SDK 내부 처리)
    # SDK나 API 스펙에 따라 25(bps) 인지 0.00025 인지 확인 필요. 위 문서상 'f': 25 로 기재됨.
    "CLIENT_ID_PREFIX": "0xba5ed1" # Client ID prefix
}

# === 3. 거래소 연결 설정 ===
EXCHANGES_CONNECTION = {
    'hyperliquid': {
        'API_URL': "https://api.hyperliquid.xyz",
        'USE_TESTNET': False,
    },
    'grvt': {
        'ENVIRONMENT': 'prod', 
    },
}

# === 4. 로깅 설정 ===
LOGGING = {
    'LEVEL': 'INFO', 
    'PORTFOLIO_FILEPATH': 'virtual_arbitrage_log.xlsx'
}


#============================================================
TARGET_PAIRS_CONFIG = {
    "0G": {
        "symbols": {
            "hyperliquid": "0G",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 84,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "2Z": {
        "symbols": {
            "hyperliquid": "2Z",
            "grvt": None,
            "pacifica": "2Z",
            "extended": None,
            "lighter": 88,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "AAVE": {
        "symbols": {
            "hyperliquid": "AAVE",
            "grvt": "AAVE_USDT_Perp",
            "pacifica": "AAVE",
            "extended": "AAVE-USD",
            "lighter": 27,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ADA": {
        "symbols": {
            "hyperliquid": "ADA",
            "grvt": "ADA_USDT_Perp",
            "pacifica": None,
            "extended": "ADA-USD",
            "lighter": 39,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "AERO": {
        "symbols": {
            "hyperliquid": "AERO",
            "grvt": None,
            "pacifica": None,
            "extended": "AERO-USD",
            "lighter": 65,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "AI16Z": {
        "symbols": {
            "hyperliquid": "AI16Z",
            "grvt": "AI16Z_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 22,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "KAITO": {
        "symbols": {
            "hyperliquid": "KAITO",
            "grvt": "KAITO_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 33,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "APEX": {
        "symbols": {
            "hyperliquid": "APEX",
            "grvt": None,
            "pacifica": None,
            "extended": "APEX-USD",
            "lighter": 86,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "APT": {
        "symbols": {
            "hyperliquid": "APT",
            "grvt": None,
            "pacifica": None,
            "extended": "APT-USD",
            "lighter": 31,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ARB": {
        "symbols": {
            "hyperliquid": "ARB",
            "grvt": "ARB_USDT_Perp",
            "pacifica": None,
            "extended": "ARB-USD",
            "lighter": 50,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ASTER": {
        "symbols": {
            "hyperliquid": "ASTER",
            "grvt": "ASTER_USDT_Perp",
            "pacifica": "ASTER",
            "extended": "ASTER-USD",
            "lighter": 83,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ATOM": {
        "symbols": {
            "hyperliquid": "ATOM",
            "grvt": "ATOM_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "AVAX": {
        "symbols": {
            "hyperliquid": "AVAX",
            "grvt": "AVAX_USDT_Perp",
            "pacifica": "AVAX",
            "extended": "AVAX-USD",
            "lighter": 9,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "AVNT": {
        "symbols": {
            "hyperliquid": "AVNT",
            "grvt": "AVNT_USDT_Perp",
            "pacifica": None,
            "extended": "AVNT-USD",
            "lighter": 82,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "BCH": {
        "symbols": {
            "hyperliquid": "BCH",
            "grvt": "BCH_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 58,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "BERA": {
        "symbols": {
            "hyperliquid": "BERA",
            "grvt": "BERA_USDT_Perp",
            "pacifica": None,
            "extended": "BERA-USD",
            "lighter": 20,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "BNB": {
        "symbols": {
            "hyperliquid": "BNB",
            "grvt": "BNB_USDT_Perp",
            "pacifica": "BNB",
            "extended": "BNB-USD",
            "lighter": 25,
        },
        "strategy_preset": "major",
        "trade_size_fixed_usd": 50.0
    },
    "1000BONK": {
        "symbols": {
            "hyperliquid": "kBONK",
            "grvt": "KBONK_USDT_Perp",
            "pacifica": "kBONK",
            "extended": None,
            "lighter": 18,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "BTC": {
        "symbols": {
            "hyperliquid": "BTC",
            "grvt": "BTC_USDT_Perp",
            "pacifica": "BTC",
            "extended": "BTC-USD",
            "lighter": 1,
        },
        "strategy_preset": "major",
        "trade_size_fixed_usd": 50.0
    },
    "CAKE": {
        "symbols": {
            "hyperliquid": "CAKE",
            "grvt": None,
            "pacifica": None,
            "extended": "CAKE-USD",
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "CC": {
        "symbols": {
            "hyperliquid": "CC",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 101,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "CFX": {
        "symbols": {
            "hyperliquid": "CFX",
            "grvt": "CFX_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "CRV": {
        "symbols": {
            "hyperliquid": "CRV",
            "grvt": "CRV_USDT_Perp",
            "pacifica": "CRV",
            "extended": "CRV-USD",
            "lighter": 36,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "DOGE": {
        "symbols": {
            "hyperliquid": "DOGE",
            "grvt": "DOGE_USDT_Perp",
            "pacifica": "DOGE",
            "extended": "DOGE-USD",
            "lighter": 3,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "DOT": {
        "symbols": {
            "hyperliquid": "DOT",
            "grvt": "DOT_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 11,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "DYDX": {
        "symbols": {
            "hyperliquid": "DYDX",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 62,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "EDEN": {
        "symbols": {
            "hyperliquid": None,
            "grvt": None,
            "pacifica": None,
            "extended": "EDEN-USD",
            "lighter": 89,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "EIGEN": {
        "symbols": {
            "hyperliquid": "EIGEN",
            "grvt": "EIGEN_USDT_Perp",
            "pacifica": None,
            "extended": "EIGEN-USD",
            "lighter": 49,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ENA": {
        "symbols": {
            "hyperliquid": "ENA",
            "grvt": "ENA_USDT_Perp",
            "pacifica": "ENA",
            "extended": "ENA-USD",
            "lighter": 29,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ETH": {
        "symbols": {
            "hyperliquid": "ETH",
            "grvt": "ETH_USDT_Perp",
            "pacifica": "ETH",
            "extended": "ETH-USD",
            "lighter": 0,
        },
        "strategy_preset": "major",
        "trade_size_fixed_usd": 50.0
    },
    "ETHFI": {
        "symbols": {
            "hyperliquid": "ETHFI",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 64,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "FARTCOIN": {
        "symbols": {
            "hyperliquid": "FARTCOIN",
            "grvt": "FARTCOIN_USDT_Perp",
            "pacifica": "FARTCOIN",
            "extended": "FARTCOIN-USD",
            "lighter": 21,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "FIL": {
        "symbols": {
            "hyperliquid": "FIL",
            "grvt": "FIL_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 103,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "1000FLOKI": {
        "symbols": {
            "hyperliquid": "kFLOKI",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 19,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "GMX": {
        "symbols": {
            "hyperliquid": "GMX",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 61,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "GOAT": {
        "symbols": {
            "hyperliquid": "GOAT",
            "grvt": None,
            "pacifica": None,
            "extended": "GOAT-USD",
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "GRASS": {
        "symbols": {
            "hyperliquid": "GRASS",
            "grvt": None,
            "pacifica": None,
            "extended": "GRASS-USD",
            "lighter": 52,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "HBAR": {
        "symbols": {
            "hyperliquid": "HBAR",
            "grvt": "HBAR_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 59,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "HYPE": {
        "symbols": {
            "hyperliquid": "HYPE",
            "grvt": "HYPE_USDT_Perp",
            "pacifica": "HYPE",
            "extended": "HYPE-USD",
            "lighter": 24,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ICP": {
        "symbols": {
            "hyperliquid": "ICP",
            "grvt": "ICP_USDT_Perp",
            "pacifica": "ICP",
            "extended": None,
            "lighter": 102,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "INIT": {
        "symbols": {
            "hyperliquid": "INIT",
            "grvt": None,
            "pacifica": None,
            "extended": "INIT-USD",
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "IP": {
        "symbols": {
            "hyperliquid": "IP",
            "grvt": "IP_USDT_Perp",
            "pacifica": None,
            "extended": "IP-USD",
            "lighter": 34,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "JUP": {
        "symbols": {
            "hyperliquid": "JUP",
            "grvt": "JUP_USDT_Perp",
            "pacifica": None,
            "extended": "JUP-USD",
            "lighter": 26,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "LAUNCHCOIN": {
        "symbols": {
            "hyperliquid": "LAUNCHCOIN",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 54,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "LDO": {
        "symbols": {
            "hyperliquid": "LDO",
            "grvt": "LDO_USDT_Perp",
            "pacifica": "LDO",
            "extended": "LDO-USD",
            "lighter": 46,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "LINEA": {
        "symbols": {
            "hyperliquid": "LINEA",
            "grvt": "LINEA_USDT_Perp",
            "pacifica": None,
            "extended": "LINEA-USD",
            "lighter": 76,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "LINK": {
        "symbols": {
            "hyperliquid": "LINK",
            "grvt": "LINK_USDT_Perp",
            "pacifica": "LINK",
            "extended": "LINK-USD",
            "lighter": 8,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "LTC": {
        "symbols": {
            "hyperliquid": "LTC",
            "grvt": "LTC_USDT_Perp",
            "pacifica": "LTC",
            "extended": "LTC-USD",
            "lighter": 35,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "MEGA": {
        "symbols": {
            "hyperliquid": "MEGA",
            "grvt": None,
            "pacifica": None,
            "extended": "MEGA-USD",
            "lighter": 94,
        },
        "strategy_preset": "pre_market",
        "trade_size_fixed_usd": 20.0
    },
    "MELANIA": {
        "symbols": {
            "hyperliquid": "MELANIA",
            "grvt": None,
            "pacifica": None,
            "extended": "MELANIA-USD",
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "MET": {
        "symbols": {
            "hyperliquid": "MET",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 95,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    # "MKR": {
    #     "symbols": {
    #         "hyperliquid": "MKR",
    #         "grvt": None,
    #         "pacifica": None,
    #         "extended": "MKR-USD",
    #         "lighter": 28,
    #     },
    #     "strategy_preset": "pre_market",
    #     "trade_size_fixed_usd": 20.0
    # },
    "MNT": {
        "symbols": {
            "hyperliquid": "MNT",
            "grvt": "MNT_USDT_Perp",
            "pacifica": None,
            "extended": "MNT-USD",
            "lighter": 63,
        },
        "strategy_preset": "pre_market",
        "trade_size_fixed_usd": 10.0
    },
    "MON": {
        "symbols": {
            "hyperliquid": "MON",
            "grvt": "MON_USDT_Perp",
            "pacifica": "MON",
            "extended": "MON-USD",
            "lighter": 91,
        },
        "strategy_preset": "pre_market",
        "trade_size_fixed_usd": 10.0
    },
    "MOODENG": {
        "symbols": {
            "hyperliquid": "MOODENG",
            "grvt": "MOODENG_USDT_Perp",
            "pacifica": None,
            "extended": "MOODENG-USD",
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "MORPHO": {
        "symbols": {
            "hyperliquid": "MORPHO",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 68,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "NEAR": {
        "symbols": {
            "hyperliquid": "NEAR",
            "grvt": "NEAR_USDT_Perp",
            "pacifica": "NEAR",
            "extended": "NEAR-USD",
            "lighter": 10,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ONDO": {
        "symbols": {
            "hyperliquid": "ONDO",
            "grvt": "ONDO_USDT_Perp",
            "pacifica": None,
            "extended": "ONDO-USD",
            "lighter": 38,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "OP": {
        "symbols": {
            "hyperliquid": "OP",
            "grvt": "OP_USDT_Perp",
            "pacifica": None,
            "extended": "OP-USD",
            "lighter": 55,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "PAXG": {
        "symbols": {
            "hyperliquid": "PAXG",
            "grvt": "PAXG_USDT_Perp",
            "pacifica": "PAXG",
            "extended": None,
            "lighter": 48,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "PENDLE": {
        "symbols": {
            "hyperliquid": "PENDLE",
            "grvt": "PENDLE_USDT_Perp",
            "pacifica": None,
            "extended": "PENDLE-USD",
            "lighter": 37,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "PENGU": {
        "symbols": {
            "hyperliquid": "PENGU",
            "grvt": "PENGU_USDT_Perp",
            "pacifica": "PENGU",
            "extended": "PENGU-USD",
            "lighter": 47,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "1000PEPE": {
        "symbols": {
            "hyperliquid": "kPEPE",
            "grvt": "KPEPE_USDT_Perp",
            "pacifica": "kPEPE",
            "extended": None,
            "lighter": 4,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "POL": {
        "symbols": {
            "hyperliquid": "POL",
            "grvt": "POL_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 14,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "POPCAT": {
        "symbols": {
            "hyperliquid": "POPCAT",
            "grvt": "POPCAT_USDT_Perp",
            "pacifica": None,
            "extended": "POPCAT-USD",
            "lighter": 23,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "PROVE": {
        "symbols": {
            "hyperliquid": "PROVE",
            "grvt": "PROVE_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 57,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "PUMP": {
        "symbols": {
            "hyperliquid": "PUMP",
            "grvt": "PUMP_USDT_Perp",
            "pacifica": "PUMP",
            "extended": "PUMP-USD",
            "lighter": 45,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "PYTH": {
        "symbols": {
            "hyperliquid": "PYTH",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 78,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "RESOLV": {
        "symbols": {
            "hyperliquid": "RESOLV",
            "grvt": "RESOLV_USDT_Perp",
            "pacifica": None,
            "extended": "RESOLV-USD",
            "lighter": 51,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "S": {
        "symbols": {
            "hyperliquid": "S",
            "grvt": None,
            "pacifica": None,
            "extended": "S-USD",
            "lighter": 40,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "SEI": {
        "symbols": {
            "hyperliquid": "SEI",
            "grvt": "SEI_USDT_Perp",
            "pacifica": None,
            "extended": "SEI-USD",
            "lighter": 32,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "1000SHIB": {
        "symbols": {
            "hyperliquid": "kSHIB",
            "grvt": "KSHIB_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": 17,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "SKY": {
        "symbols": {
            "hyperliquid": "SKY",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 79,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "SNX": {
        "symbols": {
            "hyperliquid": "SNX",
            "grvt": None,
            "pacifica": None,
            "extended": "SNX-USD",
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "SOL": {
        "symbols": {
            "hyperliquid": "SOL",
            "grvt": "SOL_USDT_Perp",
            "pacifica": "SOL",
            "extended": "SOL-USD",
            "lighter": 2,
        },
        "strategy_preset": "major",
        "trade_size_fixed_usd": 50.0
    },
    "SPX": {
        "symbols": {
            "hyperliquid": "SPX",
            "grvt": None,
            "pacifica": None,
            "extended": "SPX-USD",
            "lighter": 42,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "STBL": {
        "symbols": {
            "hyperliquid": "STBL",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 85,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "STRK": {
        "symbols": {
            "hyperliquid": "STRK",
            "grvt": "STRK_USDT_Perp",
            "pacifica": "STRK",
            "extended": "STRK-USD",
            "lighter": 104,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "SUI": {
        "symbols": {
            "hyperliquid": "SUI",
            "grvt": "SUI_USDT_Perp",
            "pacifica": "SUI",
            "extended": "SUI-USD",
            "lighter": 16,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "SYRUP": {
        "symbols": {
            "hyperliquid": "SYRUP",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 44,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "TAO": {
        "symbols": {
            "hyperliquid": "TAO",
            "grvt": "TAO_USDT_Perp",
            "pacifica": "TAO",
            "extended": "TAO-USD",
            "lighter": 13,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "TIA": {
        "symbols": {
            "hyperliquid": "TIA",
            "grvt": None,
            "pacifica": None,
            "extended": "TIA-USD",
            "lighter": 67,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "TON": {
        "symbols": {
            "hyperliquid": "TON",
            "grvt": "TON_USDT_Perp",
            "pacifica": None,
            "extended": "TON-USD",
            "lighter": 12,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "TRUMP": {
        "symbols": {
            "hyperliquid": "TRUMP",
            "grvt": "TRUMP_USDT_Perp",
            "pacifica": "TRUMP",
            "extended": "TRUMP-USD",
            "lighter": 15,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "TRX": {
        "symbols": {
            "hyperliquid": "TRX",
            "grvt": None,
            "pacifica": None,
            "extended": "TRX-USD",
            "lighter": 43,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "UNI": {
        "symbols": {
            "hyperliquid": "UNI",
            "grvt": "UNI_USDT_Perp",
            "pacifica": "UNI",
            "extended": "UNI-USD",
            "lighter": 30,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "VINE": {
        "symbols": {
            "hyperliquid": "VINE",
            "grvt": "VINE_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "VIRTUAL": {
        "symbols": {
            "hyperliquid": "VIRTUAL",
            "grvt": "VIRTUAL_USDT_Perp",
            "pacifica": "VIRTUAL",
            "extended": "VIRTUAL-USD",
            "lighter": 41,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "VVV": {
        "symbols": {
            "hyperliquid": "VVV",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 69,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "W": {
        "symbols": {
            "hyperliquid": "W",
            "grvt": "W_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "WIF": {
        "symbols": {
            "hyperliquid": "WIF",
            "grvt": "WIF_USDT_Perp",
            "pacifica": None,
            "extended": "WIF-USD",
            "lighter": 5,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "WLD": {
        "symbols": {
            "hyperliquid": "WLD",
            "grvt": "WLD_USDT_Perp",
            "pacifica": None,
            "extended": "WLD-USD",
            "lighter": 6,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "WLFI": {
        "symbols": {
            "hyperliquid": "WLFI",
            "grvt": "WLFI_USDT_Perp",
            "pacifica": "WLFI",
            "extended": "WLFI-USD",
            "lighter": 72,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "XLM": {
        "symbols": {
            "hyperliquid": "XLM",
            "grvt": "XLM_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "XPL": {
        "symbols": {
            "hyperliquid": "XPL",
            "grvt": "XPL_USDT_Perp",
            "pacifica": "XPL",
            "extended": "XPL-USD",
            "lighter": 71,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "XRP": {
        "symbols": {
            "hyperliquid": "XRP",
            "grvt": "XRP_USDT_Perp",
            "pacifica": "XRP",
            "extended": "XRP-USD",
            "lighter": 7,
        },
        "strategy_preset": "major",
        "trade_size_fixed_usd": 50.0
    },
    "YZY": {
        "symbols": {
            "hyperliquid": "YZY",
            "grvt": None,
            "pacifica": None,
            "extended": None,
            "lighter": 70,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ZEC": {
        "symbols": {
            "hyperliquid": "ZEC",
            "grvt": "ZEC_USDT_Perp",
            "pacifica": "ZEC",
            "extended": "ZEC-USD",
            "lighter": 90,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ZEN": {
        "symbols": {
            "hyperliquid": "ZEN",
            "grvt": "ZEN_USDT_Perp",
            "pacifica": None,
            "extended": None,
            "lighter": None,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ZK": {
        "symbols": {
            "hyperliquid": "ZK",
            "grvt": "ZK_USDT_Perp",
            "pacifica": "ZK",
            "extended": None,
            "lighter": 56,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ZORA": {
        "symbols": {
            "hyperliquid": "ZORA",
            "grvt": None,
            "pacifica": None,
            "extended": "ZORA-USD",
            "lighter": 53,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
    "ZRO": {
        "symbols": {
            "hyperliquid": "ZRO",
            "grvt": None,
            "pacifica": None,
            "extended": "ZRO-USD",
            "lighter": 60,
        },
        "strategy_preset": "volatile",
        "trade_size_fixed_usd": 20.0
    },
}
