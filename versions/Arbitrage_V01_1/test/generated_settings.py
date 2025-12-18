# === 2. 거래 대상 페어 및 전략 매핑 (자동 생성됨) ===
TARGET_PAIRS_CONFIG = {
    "ADA": {
        "symbols": {
            "hyperliquid": "ADA",
            "grvt": "ADA_USDT_Perp",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 30.0
    },
    "BNB": {
        "symbols": {
            "hyperliquid": "BNB",
            "grvt": "BNB_USDT_Perp",
            "pacifica": "BNB",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 50.0
    },
    "BTC": {
        "symbols": {
            "hyperliquid": "BTC",
            "grvt": "BTC_USDT_Perp",
            "pacifica": "BTC",
        },
        "strategy_preset": "major",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 50.0
    },
    "ETH": {
        "symbols": {
            "hyperliquid": "ETH",
            "grvt": "ETH_USDT_Perp",
            "pacifica": "ETH",
        },
        "strategy_preset": "major",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 50.0
    },
    "HYPE": {
        "symbols": {
            "hyperliquid": "HYPE",
            "grvt": "HYPE_USDT_Perp",
            "pacifica": "HYPE",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 50.0
    },
    "SOL": {
        "symbols": {
            "hyperliquid": "SOL",
            "grvt": "SOL_USDT_Perp",
            "pacifica": "SOL",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 50.0
    },
    "WLD": {
        "symbols": {
            "hyperliquid": "WLD",
            "grvt": "WLD_USDT_Perp",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 30.0
    },
    "WLFI": {
        "symbols": {
            "hyperliquid": "WLFI",
            "grvt": "WLFI_USDT_Perp",
            "pacifica": "WLFI",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 30.0
    },
    "XPL": {
        "symbols": {
            "hyperliquid": "XPL",
            "grvt": "XPL_USDT_Perp",
            "pacifica": "XPL",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 30.0
    },
    "XRP": {
        "symbols": {
            "hyperliquid": "XRP",
            "grvt": "XRP_USDT_Perp",
            "pacifica": "XRP",
        },
        "strategy_preset": "alt",  # [고정 설정]
        "trade_size_pct": None,
        "trade_size_fixed_usd": 30.0
    },
    "0G": {
        "symbols": {
            "hyperliquid": "0G",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "2Z": {
        "symbols": {
            "hyperliquid": "2Z",
            "pacifica": "2Z",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AAVE": {
        "symbols": {
            "hyperliquid": "AAVE",
            "grvt": "AAVE_USDT_Perp",
            "pacifica": "AAVE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ACE": {
        "symbols": {
            "hyperliquid": "ACE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AERO": {
        "symbols": {
            "hyperliquid": "AERO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AI": {
        "symbols": {
            "hyperliquid": "AI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AI16Z": {
        "symbols": {
            "hyperliquid": "AI16Z",
            "grvt": "AI16Z_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AIXBT": {
        "symbols": {
            "hyperliquid": "AIXBT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ALGO": {
        "symbols": {
            "hyperliquid": "ALGO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ALT": {
        "symbols": {
            "hyperliquid": "ALT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ANIME": {
        "symbols": {
            "hyperliquid": "ANIME",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "APE": {
        "symbols": {
            "hyperliquid": "APE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "APEX": {
        "symbols": {
            "hyperliquid": "APEX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "APT": {
        "symbols": {
            "hyperliquid": "APT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AR": {
        "symbols": {
            "hyperliquid": "AR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ARB": {
        "symbols": {
            "hyperliquid": "ARB",
            "grvt": "ARB_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ARK": {
        "symbols": {
            "hyperliquid": "ARK",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ASTER": {
        "symbols": {
            "hyperliquid": "ASTER",
            "grvt": "ASTER_USDT_Perp",
            "pacifica": "ASTER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ATOM": {
        "symbols": {
            "hyperliquid": "ATOM",
            "grvt": "ATOM_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AVAX": {
        "symbols": {
            "hyperliquid": "AVAX",
            "grvt": "AVAX_USDT_Perp",
            "pacifica": "AVAX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "AVNT": {
        "symbols": {
            "hyperliquid": "AVNT",
            "grvt": "AVNT_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BABY": {
        "symbols": {
            "hyperliquid": "BABY",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BADGER": {
        "symbols": {
            "hyperliquid": "BADGER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BANANA": {
        "symbols": {
            "hyperliquid": "BANANA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BARD": {
        "symbols": {
            "grvt": "BARD_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BCH": {
        "symbols": {
            "hyperliquid": "BCH",
            "grvt": "BCH_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BERA": {
        "symbols": {
            "hyperliquid": "BERA",
            "grvt": "BERA_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BIGTIME": {
        "symbols": {
            "hyperliquid": "BIGTIME",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BIO": {
        "symbols": {
            "hyperliquid": "BIO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BLAST": {
        "symbols": {
            "hyperliquid": "BLAST",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BLESS": {
        "symbols": {
            "grvt": "BLESS_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BLUR": {
        "symbols": {
            "hyperliquid": "BLUR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BLZ": {
        "symbols": {
            "hyperliquid": "BLZ",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BNT": {
        "symbols": {
            "hyperliquid": "BNT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BOME": {
        "symbols": {
            "hyperliquid": "BOME",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BRETT": {
        "symbols": {
            "hyperliquid": "BRETT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "BSV": {
        "symbols": {
            "hyperliquid": "BSV",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CAKE": {
        "symbols": {
            "hyperliquid": "CAKE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CANTO": {
        "symbols": {
            "hyperliquid": "CANTO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CATI": {
        "symbols": {
            "hyperliquid": "CATI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CC": {
        "symbols": {
            "hyperliquid": "CC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CELO": {
        "symbols": {
            "hyperliquid": "CELO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CFX": {
        "symbols": {
            "hyperliquid": "CFX",
            "grvt": "CFX_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CHILLGUY": {
        "symbols": {
            "hyperliquid": "CHILLGUY",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "COAI": {
        "symbols": {
            "grvt": "COAI_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "COMP": {
        "symbols": {
            "hyperliquid": "COMP",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CRV": {
        "symbols": {
            "hyperliquid": "CRV",
            "grvt": "CRV_USDT_Perp",
            "pacifica": "CRV",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "CYBER": {
        "symbols": {
            "hyperliquid": "CYBER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "DOGE": {
        "symbols": {
            "hyperliquid": "DOGE",
            "grvt": "DOGE_USDT_Perp",
            "pacifica": "DOGE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "DOOD": {
        "symbols": {
            "hyperliquid": "DOOD",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "DOT": {
        "symbols": {
            "hyperliquid": "DOT",
            "grvt": "DOT_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "DYDX": {
        "symbols": {
            "hyperliquid": "DYDX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "DYM": {
        "symbols": {
            "hyperliquid": "DYM",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "EIGEN": {
        "symbols": {
            "hyperliquid": "EIGEN",
            "grvt": "EIGEN_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ENA": {
        "symbols": {
            "hyperliquid": "ENA",
            "grvt": "ENA_USDT_Perp",
            "pacifica": "ENA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ENS": {
        "symbols": {
            "hyperliquid": "ENS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ETC": {
        "symbols": {
            "hyperliquid": "ETC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ETHFI": {
        "symbols": {
            "hyperliquid": "ETHFI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FARTCOIN": {
        "symbols": {
            "hyperliquid": "FARTCOIN",
            "grvt": "FARTCOIN_USDT_Perp",
            "pacifica": "FARTCOIN",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FET": {
        "symbols": {
            "hyperliquid": "FET",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FIL": {
        "symbols": {
            "hyperliquid": "FIL",
            "grvt": "FIL_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FRIEND": {
        "symbols": {
            "hyperliquid": "FRIEND",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FTM": {
        "symbols": {
            "hyperliquid": "FTM",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FTT": {
        "symbols": {
            "hyperliquid": "FTT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "FXS": {
        "symbols": {
            "hyperliquid": "FXS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GALA": {
        "symbols": {
            "hyperliquid": "GALA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GAS": {
        "symbols": {
            "hyperliquid": "GAS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GIGGLE": {
        "symbols": {
            "grvt": "GIGGLE_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GMT": {
        "symbols": {
            "hyperliquid": "GMT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GMX": {
        "symbols": {
            "hyperliquid": "GMX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GOAT": {
        "symbols": {
            "hyperliquid": "GOAT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GRASS": {
        "symbols": {
            "hyperliquid": "GRASS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "GRIFFAIN": {
        "symbols": {
            "hyperliquid": "GRIFFAIN",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "H": {
        "symbols": {
            "grvt": "H_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "HBAR": {
        "symbols": {
            "hyperliquid": "HBAR",
            "grvt": "HBAR_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "HEMI": {
        "symbols": {
            "hyperliquid": "HEMI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "HMSTR": {
        "symbols": {
            "hyperliquid": "HMSTR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "HPOS": {
        "symbols": {
            "hyperliquid": "HPOS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "HYPER": {
        "symbols": {
            "hyperliquid": "HYPER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ICP": {
        "symbols": {
            "hyperliquid": "ICP",
            "grvt": "ICP_USDT_Perp",
            "pacifica": "ICP",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ILV": {
        "symbols": {
            "hyperliquid": "ILV",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "IMX": {
        "symbols": {
            "hyperliquid": "IMX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "INIT": {
        "symbols": {
            "hyperliquid": "INIT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "INJ": {
        "symbols": {
            "hyperliquid": "INJ",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "IO": {
        "symbols": {
            "hyperliquid": "IO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "IOTA": {
        "symbols": {
            "hyperliquid": "IOTA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "IP": {
        "symbols": {
            "hyperliquid": "IP",
            "grvt": "IP_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "JELLY": {
        "symbols": {
            "hyperliquid": "JELLY",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "JTO": {
        "symbols": {
            "hyperliquid": "JTO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "JUP": {
        "symbols": {
            "hyperliquid": "JUP",
            "grvt": "JUP_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KAITO": {
        "symbols": {
            "hyperliquid": "KAITO",
            "grvt": "KAITO_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KAS": {
        "symbols": {
            "hyperliquid": "KAS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KBONK": {
        "symbols": {
            "hyperliquid": "kBONK",
            "grvt": "KBONK_USDT_Perp",
            "pacifica": "kBONK",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KDOGS": {
        "symbols": {
            "hyperliquid": "kDOGS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KFLOKI": {
        "symbols": {
            "hyperliquid": "kFLOKI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KLUNC": {
        "symbols": {
            "hyperliquid": "kLUNC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KNEIRO": {
        "symbols": {
            "hyperliquid": "kNEIRO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KPEPE": {
        "symbols": {
            "hyperliquid": "kPEPE",
            "grvt": "KPEPE_USDT_Perp",
            "pacifica": "kPEPE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "KSHIB": {
        "symbols": {
            "hyperliquid": "kSHIB",
            "grvt": "KSHIB_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LA": {
        "symbols": {
            "grvt": "LA_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LAUNCHCOIN": {
        "symbols": {
            "hyperliquid": "LAUNCHCOIN",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LAYER": {
        "symbols": {
            "hyperliquid": "LAYER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LDO": {
        "symbols": {
            "hyperliquid": "LDO",
            "grvt": "LDO_USDT_Perp",
            "pacifica": "LDO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LINEA": {
        "symbols": {
            "hyperliquid": "LINEA",
            "grvt": "LINEA_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LINK": {
        "symbols": {
            "hyperliquid": "LINK",
            "grvt": "LINK_USDT_Perp",
            "pacifica": "LINK",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LISTA": {
        "symbols": {
            "hyperliquid": "LISTA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LOOM": {
        "symbols": {
            "hyperliquid": "LOOM",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "LTC": {
        "symbols": {
            "hyperliquid": "LTC",
            "grvt": "LTC_USDT_Perp",
            "pacifica": "LTC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MANTA": {
        "symbols": {
            "hyperliquid": "MANTA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MATIC": {
        "symbols": {
            "hyperliquid": "MATIC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MAV": {
        "symbols": {
            "hyperliquid": "MAV",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MAVIA": {
        "symbols": {
            "hyperliquid": "MAVIA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ME": {
        "symbols": {
            "hyperliquid": "ME",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MEGA": {
        "symbols": {
            "hyperliquid": "MEGA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MELANIA": {
        "symbols": {
            "hyperliquid": "MELANIA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MEME": {
        "symbols": {
            "hyperliquid": "MEME",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MERL": {
        "symbols": {
            "hyperliquid": "MERL",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MET": {
        "symbols": {
            "hyperliquid": "MET",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MEW": {
        "symbols": {
            "hyperliquid": "MEW",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MINA": {
        "symbols": {
            "hyperliquid": "MINA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MKR": {
        "symbols": {
            "hyperliquid": "MKR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MNT": {
        "symbols": {
            "hyperliquid": "MNT",
            "grvt": "MNT_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MON": {
        "symbols": {
            "hyperliquid": "MON",
            "grvt": "MON_USDT_Perp",
            "pacifica": "MON",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MOODENG": {
        "symbols": {
            "hyperliquid": "MOODENG",
            "grvt": "MOODENG_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MORPHO": {
        "symbols": {
            "hyperliquid": "MORPHO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MOVE": {
        "symbols": {
            "hyperliquid": "MOVE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "MYRO": {
        "symbols": {
            "hyperliquid": "MYRO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NEAR": {
        "symbols": {
            "hyperliquid": "NEAR",
            "grvt": "NEAR_USDT_Perp",
            "pacifica": "NEAR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NEIROETH": {
        "symbols": {
            "hyperliquid": "NEIROETH",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NEO": {
        "symbols": {
            "hyperliquid": "NEO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NFTI": {
        "symbols": {
            "hyperliquid": "NFTI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NIL": {
        "symbols": {
            "hyperliquid": "NIL",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NOT": {
        "symbols": {
            "hyperliquid": "NOT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NTRN": {
        "symbols": {
            "hyperliquid": "NTRN",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "NXPC": {
        "symbols": {
            "hyperliquid": "NXPC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "OGN": {
        "symbols": {
            "hyperliquid": "OGN",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "OM": {
        "symbols": {
            "hyperliquid": "OM",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "OMNI": {
        "symbols": {
            "hyperliquid": "OMNI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ONDO": {
        "symbols": {
            "hyperliquid": "ONDO",
            "grvt": "ONDO_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "OP": {
        "symbols": {
            "hyperliquid": "OP",
            "grvt": "OP_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ORBS": {
        "symbols": {
            "hyperliquid": "ORBS",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ORDI": {
        "symbols": {
            "hyperliquid": "ORDI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "OX": {
        "symbols": {
            "hyperliquid": "OX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PANDORA": {
        "symbols": {
            "hyperliquid": "PANDORA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PAXG": {
        "symbols": {
            "hyperliquid": "PAXG",
            "pacifica": "PAXG",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PENDLE": {
        "symbols": {
            "hyperliquid": "PENDLE",
            "grvt": "PENDLE_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PENGU": {
        "symbols": {
            "hyperliquid": "PENGU",
            "grvt": "PENGU_USDT_Perp",
            "pacifica": "PENGU",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PEOPLE": {
        "symbols": {
            "hyperliquid": "PEOPLE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PIXEL": {
        "symbols": {
            "hyperliquid": "PIXEL",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PNUT": {
        "symbols": {
            "hyperliquid": "PNUT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "POL": {
        "symbols": {
            "hyperliquid": "POL",
            "grvt": "POL_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "POLYX": {
        "symbols": {
            "hyperliquid": "POLYX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "POPCAT": {
        "symbols": {
            "hyperliquid": "POPCAT",
            "grvt": "POPCAT_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PROMPT": {
        "symbols": {
            "hyperliquid": "PROMPT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PROVE": {
        "symbols": {
            "hyperliquid": "PROVE",
            "grvt": "PROVE_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PUMP": {
        "symbols": {
            "hyperliquid": "PUMP",
            "grvt": "PUMP_USDT_Perp",
            "pacifica": "PUMP",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PURR": {
        "symbols": {
            "hyperliquid": "PURR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "PYTH": {
        "symbols": {
            "hyperliquid": "PYTH",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RDNT": {
        "symbols": {
            "hyperliquid": "RDNT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RENDER": {
        "symbols": {
            "hyperliquid": "RENDER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "REQ": {
        "symbols": {
            "hyperliquid": "REQ",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RESOLV": {
        "symbols": {
            "hyperliquid": "RESOLV",
            "grvt": "RESOLV_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "REZ": {
        "symbols": {
            "hyperliquid": "REZ",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RLB": {
        "symbols": {
            "hyperliquid": "RLB",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RNDR": {
        "symbols": {
            "hyperliquid": "RNDR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RSR": {
        "symbols": {
            "hyperliquid": "RSR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "RUNE": {
        "symbols": {
            "hyperliquid": "RUNE",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "S": {
        "symbols": {
            "hyperliquid": "S",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SAGA": {
        "symbols": {
            "hyperliquid": "SAGA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SAHARA": {
        "symbols": {
            "grvt": "SAHARA_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SAND": {
        "symbols": {
            "hyperliquid": "SAND",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SCR": {
        "symbols": {
            "hyperliquid": "SCR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SEI": {
        "symbols": {
            "hyperliquid": "SEI",
            "grvt": "SEI_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SHIA": {
        "symbols": {
            "hyperliquid": "SHIA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SKY": {
        "symbols": {
            "hyperliquid": "SKY",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SNX": {
        "symbols": {
            "hyperliquid": "SNX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SOPH": {
        "symbols": {
            "hyperliquid": "SOPH",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SPX": {
        "symbols": {
            "hyperliquid": "SPX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "STBL": {
        "symbols": {
            "hyperliquid": "STBL",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "STG": {
        "symbols": {
            "hyperliquid": "STG",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "STRAX": {
        "symbols": {
            "hyperliquid": "STRAX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "STRK": {
        "symbols": {
            "hyperliquid": "STRK",
            "grvt": "STRK_USDT_Perp",
            "pacifica": "STRK",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "STX": {
        "symbols": {
            "hyperliquid": "STX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SUI": {
        "symbols": {
            "hyperliquid": "SUI",
            "grvt": "SUI_USDT_Perp",
            "pacifica": "SUI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SUPER": {
        "symbols": {
            "hyperliquid": "SUPER",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SUSHI": {
        "symbols": {
            "hyperliquid": "SUSHI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "SYRUP": {
        "symbols": {
            "hyperliquid": "SYRUP",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TAO": {
        "symbols": {
            "hyperliquid": "TAO",
            "pacifica": "TAO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TIA": {
        "symbols": {
            "hyperliquid": "TIA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TNSR": {
        "symbols": {
            "hyperliquid": "TNSR",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TON": {
        "symbols": {
            "hyperliquid": "TON",
            "grvt": "TON_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TRB": {
        "symbols": {
            "hyperliquid": "TRB",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TRUMP": {
        "symbols": {
            "hyperliquid": "TRUMP",
            "grvt": "TRUMP_USDT_Perp",
            "pacifica": "TRUMP",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TRX": {
        "symbols": {
            "hyperliquid": "TRX",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TST": {
        "symbols": {
            "hyperliquid": "TST",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "TURBO": {
        "symbols": {
            "hyperliquid": "TURBO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "UMA": {
        "symbols": {
            "hyperliquid": "UMA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "UNI": {
        "symbols": {
            "hyperliquid": "UNI",
            "grvt": "UNI_USDT_Perp",
            "pacifica": "UNI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "UNIBOT": {
        "symbols": {
            "hyperliquid": "UNIBOT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "USTC": {
        "symbols": {
            "hyperliquid": "USTC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "USUAL": {
        "symbols": {
            "hyperliquid": "USUAL",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "VINE": {
        "symbols": {
            "hyperliquid": "VINE",
            "grvt": "VINE_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "VIRTUAL": {
        "symbols": {
            "hyperliquid": "VIRTUAL",
            "grvt": "VIRTUAL_USDT_Perp",
            "pacifica": "VIRTUAL",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "VVV": {
        "symbols": {
            "hyperliquid": "VVV",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "W": {
        "symbols": {
            "hyperliquid": "W",
            "grvt": "W_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "WCT": {
        "symbols": {
            "hyperliquid": "WCT",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "WIF": {
        "symbols": {
            "hyperliquid": "WIF",
            "grvt": "WIF_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "XAI": {
        "symbols": {
            "hyperliquid": "XAI",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "XLM": {
        "symbols": {
            "hyperliquid": "XLM",
            "grvt": "XLM_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "YGG": {
        "symbols": {
            "hyperliquid": "YGG",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "YZY": {
        "symbols": {
            "hyperliquid": "YZY",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZEC": {
        "symbols": {
            "hyperliquid": "ZEC",
            "grvt": "ZEC_USDT_Perp",
            "pacifica": "ZEC",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZEN": {
        "symbols": {
            "hyperliquid": "ZEN",
            "grvt": "ZEN_USDT_Perp",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZEREBRO": {
        "symbols": {
            "hyperliquid": "ZEREBRO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZETA": {
        "symbols": {
            "hyperliquid": "ZETA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZK": {
        "symbols": {
            "hyperliquid": "ZK",
            "grvt": "ZK_USDT_Perp",
            "pacifica": "ZK",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZORA": {
        "symbols": {
            "hyperliquid": "ZORA",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
    "ZRO": {
        "symbols": {
            "hyperliquid": "ZRO",
        },
        "strategy_preset": "volatile",
        "trade_size_pct": None,
        "trade_size_fixed_usd": 20.0
    },
}