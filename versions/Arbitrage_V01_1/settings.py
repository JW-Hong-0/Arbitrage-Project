# settings.py
# (⭐️ 최종 버전: 다중 거래소 매핑, 전략 그룹화, %/고정 금액 동시 지원)
#cd /d D:\Program_Files\Crypto\HyperLiquid\Arbitrage_V01_1
#python arbitrage_bot.py
#python run_ui.py
#python gui_dashboard_V3.py
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
    
    # 수수료율 (Decimal 계산용)
    'FEES': {
        'hyperliquid': 0.0432, # Taker Fee
        'grvt': 0.045,
        'pacifica': 0.06,
        'extended': 0.025,
        'lighter': 0.0
    },
    
    'VIRTUAL_LEVERAGE': 3.0,
    'HEALTH_CHECK_INTERVAL_SEC': 10 
}

# 포지션 관리 설정
POSITION_MAX_HOLD_SECONDS = 3600  # 1시간 뒤 강제 청산
POSITION_MIN_HOLD_SECONDS = 60    # 최소 1분 보유 (노이즈 방어)

# === 2. 전략 프리셋 (Strategy Presets) ===
STRATEGY_PRESETS = {
    "major": { 
        "entry_threshold_pct": 0.35, 
        "exit_threshold_pct": -0.05 
    },
    "alt": { 
        "entry_threshold_pct": 0.6, 
        "exit_threshold_pct": -0.05 
    },
    "volatile": { 
        "entry_threshold_pct": 1.0, 
        "exit_threshold_pct": -0.1 
    },
    "pre_market": { 
        "entry_threshold_pct": 5.0, 
        "exit_threshold_pct": -15.0 
    }
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

TARGET_PAIRS_CONFIG = {

    "AVAX": {

        "symbols": {

            "hyperliquid": "AVAX",

            "grvt": "AVAX_USDT_Perp",

            "pacifica": "AVAX",

            "extended": "AVAX-USD",

            "lighter": 9,

        },

        "strategy_preset": "major",

        "trade_size_fixed_usd": 50.0

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

    "DOGE": {

        "symbols": {

            "hyperliquid": "DOGE",

            "grvt": "DOGE_USDT_Perp",

            "pacifica": "DOGE",

            "extended": "DOGE-USD",

            "lighter": 3,

        },

        "strategy_preset": "major",

        "trade_size_fixed_usd": 50.0

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

    "SUI": {

        "symbols": {

            "hyperliquid": "SUI",

            "grvt": "SUI_USDT_Perp",

            "pacifica": "SUI",

            "extended": "SUI-USD",

            "lighter": 16,

        },

        "strategy_preset": "major",

        "trade_size_fixed_usd": 50.0

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

    "0G": {

        "symbols": {

            "hyperliquid": "0G",

            "grvt": "0G_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 84,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "1000BONK": {

        "symbols": {

            "hyperliquid": "1000BONK",

            "grvt": "1000BONK_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 18,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "1000FLOKI": {

        "symbols": {

            "hyperliquid": "1000FLOKI",

            "grvt": "1000FLOKI_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 19,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "1000PEPE": {

        "symbols": {

            "hyperliquid": "1000PEPE",

            "grvt": "1000PEPE_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 4,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "1000SHIB": {

        "symbols": {

            "hyperliquid": "1000SHIB",

            "grvt": "1000SHIB_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 17,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "1000TOSHI": {

        "symbols": {

            "hyperliquid": "1000TOSHI",

            "grvt": "1000TOSHI_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 81,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "2Z": {

        "symbols": {

            "hyperliquid": "2Z",

            "grvt": "2Z_USDT_Perp",

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

            "extended": None,

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

            "extended": None,

            "lighter": 39,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "AERO": {

        "symbols": {

            "hyperliquid": "AERO",

            "grvt": "AERO_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

    "APEX": {

        "symbols": {

            "hyperliquid": "APEX",

            "grvt": "APEX_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 86,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "APT": {

        "symbols": {

            "hyperliquid": "APT",

            "grvt": "APT_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

            "lighter": 83,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "AUDUSD": {

        "symbols": {

            "hyperliquid": "AUDUSD",

            "grvt": "AUDUSD_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 106,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "AVNT": {

        "symbols": {

            "hyperliquid": "AVNT",

            "grvt": "AVNT_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

            "lighter": 20,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "CC": {

        "symbols": {

            "hyperliquid": "CC",

            "grvt": "CC_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 101,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "COIN": {

        "symbols": {

            "hyperliquid": "COIN",

            "grvt": "COIN_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 109,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "CRO": {

        "symbols": {

            "hyperliquid": "CRO",

            "grvt": "CRO_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 73,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "CRV": {

        "symbols": {

            "hyperliquid": "CRV",

            "grvt": "CRV_USDT_Perp",

            "pacifica": "CRV",

            "extended": None,

            "lighter": 36,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "DOLO": {

        "symbols": {

            "hyperliquid": "DOLO",

            "grvt": "DOLO_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 75,

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

            "grvt": "DYDX_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 62,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "EDEN": {

        "symbols": {

            "hyperliquid": "EDEN",

            "grvt": "EDEN_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

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

            "extended": None,

            "lighter": 29,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "ETHFI": {

        "symbols": {

            "hyperliquid": "ETHFI",

            "grvt": "ETHFI_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 64,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "EURUSD": {

        "symbols": {

            "hyperliquid": "EURUSD",

            "grvt": "EURUSD_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 96,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "FARTCOIN": {

        "symbols": {

            "hyperliquid": "FARTCOIN",

            "grvt": "FARTCOIN_USDT_Perp",

            "pacifica": "FARTCOIN",

            "extended": None,

            "lighter": 21,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "FF": {

        "symbols": {

            "hyperliquid": "FF",

            "grvt": "FF_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 87,

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

    "GBPUSD": {

        "symbols": {

            "hyperliquid": "GBPUSD",

            "grvt": "GBPUSD_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 97,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "GMX": {

        "symbols": {

            "hyperliquid": "GMX",

            "grvt": "GMX_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 61,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "GRASS": {

        "symbols": {

            "hyperliquid": "GRASS",

            "grvt": "GRASS_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

    "HOOD": {

        "symbols": {

            "hyperliquid": "HOOD",

            "grvt": "HOOD_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 108,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "HYPE": {

        "symbols": {

            "hyperliquid": "HYPE",

            "grvt": "HYPE_USDT_Perp",

            "pacifica": "HYPE",

            "extended": None,

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

    "IP": {

        "symbols": {

            "hyperliquid": "IP",

            "grvt": "IP_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

            "lighter": 26,

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

    "LAUNCHCOIN": {

        "symbols": {

            "hyperliquid": "LAUNCHCOIN",

            "grvt": "LAUNCHCOIN_USDT_Perp",

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

            "extended": None,

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

            "extended": None,

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

            "grvt": "MEGA_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 94,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "MET": {

        "symbols": {

            "hyperliquid": "MET",

            "grvt": "MET_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 95,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "MKR": {

        "symbols": {

            "hyperliquid": "MKR",

            "grvt": "MKR_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 28,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "MNT": {

        "symbols": {

            "hyperliquid": "MNT",

            "grvt": "MNT_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 63,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "MON": {

        "symbols": {

            "hyperliquid": "MON",

            "grvt": "MON_USDT_Perp",

            "pacifica": "MON",

            "extended": None,

            "lighter": 91,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "MORPHO": {

        "symbols": {

            "hyperliquid": "MORPHO",

            "grvt": "MORPHO_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 68,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "MYX": {

        "symbols": {

            "hyperliquid": "MYX",

            "grvt": "MYX_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 80,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "NEAR": {

        "symbols": {

            "hyperliquid": "NEAR",

            "grvt": "NEAR_USDT_Perp",

            "pacifica": "NEAR",

            "extended": None,

            "lighter": 10,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "NMR": {

        "symbols": {

            "hyperliquid": "NMR",

            "grvt": "NMR_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 74,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "NVDA": {

        "symbols": {

            "hyperliquid": "NVDA",

            "grvt": "NVDA_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 110,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "NZDUSD": {

        "symbols": {

            "hyperliquid": "NZDUSD",

            "grvt": "NZDUSD_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 107,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "ONDO": {

        "symbols": {

            "hyperliquid": "ONDO",

            "grvt": "ONDO_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

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

            "extended": None,

            "lighter": 47,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "PLTR": {

        "symbols": {

            "hyperliquid": "PLTR",

            "grvt": "PLTR_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 111,

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

            "extended": None,

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

            "extended": None,

            "lighter": 45,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "PYTH": {

        "symbols": {

            "hyperliquid": "PYTH",

            "grvt": "PYTH_USDT_Perp",

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

            "extended": None,

            "lighter": 51,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "S": {

        "symbols": {

            "hyperliquid": "S",

            "grvt": "S_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

            "lighter": 32,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "SKY": {

        "symbols": {

            "hyperliquid": "SKY",

            "grvt": "SKY_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 79,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "SPX": {

        "symbols": {

            "hyperliquid": "SPX",

            "grvt": "SPX_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 42,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "STBL": {

        "symbols": {

            "hyperliquid": "STBL",

            "grvt": "STBL_USDT_Perp",

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

    "SYRUP": {

        "symbols": {

            "hyperliquid": "SYRUP",

            "grvt": "SYRUP_USDT_Perp",

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

            "extended": None,

            "lighter": 13,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "TIA": {

        "symbols": {

            "hyperliquid": "TIA",

            "grvt": "TIA_USDT_Perp",

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

            "extended": None,

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

            "grvt": "TRX_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 43,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "TSLA": {

        "symbols": {

            "hyperliquid": "TSLA",

            "grvt": "TSLA_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 112,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "UNI": {

        "symbols": {

            "hyperliquid": "UNI",

            "grvt": "UNI_USDT_Perp",

            "pacifica": "UNI",

            "extended": None,

            "lighter": 30,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "USDCAD": {

        "symbols": {

            "hyperliquid": "USDCAD",

            "grvt": "USDCAD_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 100,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "USDCHF": {

        "symbols": {

            "hyperliquid": "USDCHF",

            "grvt": "USDCHF_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 99,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "USDJPY": {

        "symbols": {

            "hyperliquid": "USDJPY",

            "grvt": "USDJPY_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 98,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "USDKRW": {

        "symbols": {

            "hyperliquid": "USDKRW",

            "grvt": "USDKRW_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 105,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "USELESS": {

        "symbols": {

            "hyperliquid": "USELESS",

            "grvt": "USELESS_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 66,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "VIRTUAL": {

        "symbols": {

            "hyperliquid": "VIRTUAL",

            "grvt": "VIRTUAL_USDT_Perp",

            "pacifica": "VIRTUAL",

            "extended": None,

            "lighter": 41,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "VVV": {

        "symbols": {

            "hyperliquid": "VVV",

            "grvt": "VVV_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 69,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "WIF": {

        "symbols": {

            "hyperliquid": "WIF",

            "grvt": "WIF_USDT_Perp",

            "pacifica": None,

            "extended": None,

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

            "extended": None,

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

            "extended": None,

            "lighter": 72,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "XAG": {

        "symbols": {

            "hyperliquid": "XAG",

            "grvt": "XAG_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 93,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "XAU": {

        "symbols": {

            "hyperliquid": "XAU",

            "grvt": "XAU_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 92,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "XMR": {

        "symbols": {

            "hyperliquid": "XMR",

            "grvt": "XMR_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 77,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "XPL": {

        "symbols": {

            "hyperliquid": "XPL",

            "grvt": "XPL_USDT_Perp",

            "pacifica": "XPL",

            "extended": None,

            "lighter": 71,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "YZY": {

        "symbols": {

            "hyperliquid": "YZY",

            "grvt": "YZY_USDT_Perp",

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

            "extended": None,

            "lighter": 90,

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

            "grvt": "ZORA_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 53,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "ZRO": {

        "symbols": {

            "hyperliquid": "ZRO",

            "grvt": "ZRO_USDT_Perp",

            "pacifica": None,

            "extended": None,

            "lighter": 60,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "kBONK": {

        "symbols": {

            "hyperliquid": "kBONK",

            "grvt": "kBONK_USDT_Perp",

            "pacifica": "kBONK",

            "extended": None,

            "lighter": None,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

    "kPEPE": {

        "symbols": {

            "hyperliquid": "kPEPE",

            "grvt": "kPEPE_USDT_Perp",

            "pacifica": "kPEPE",

            "extended": None,

            "lighter": None,

        },

        "strategy_preset": "volatile",

        "trade_size_fixed_usd": 20.0

    },

}