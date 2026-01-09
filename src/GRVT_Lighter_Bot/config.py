import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Environment Settings
    GRVT_ENV = os.getenv("GRVT_ENV", "PROD")  # TESTNET or PROD
    LIGHTER_ENV = os.getenv("LIGHTER_ENV", "MAINNET") # TESTNET or MAINNET
    
    # Load keys based on Environment
    if GRVT_ENV == "TESTNET":
        GRVT_API_KEY = os.getenv("GRVT_TESTNET_API_KEY")
        GRVT_PRIVATE_KEY = os.getenv("GRVT_TESTNET_SECRET_KEY")
        GRVT_TRADING_ACCOUNT_ID = os.getenv("GRVT_TESTNET_TRADING_ACCOUNT_ID")
    else:
        GRVT_API_KEY = os.getenv("GRVT_MAINNET_API_KEY")
        GRVT_PRIVATE_KEY = os.getenv("GRVT_MAINNET_SECRET_KEY")
        GRVT_TRADING_ACCOUNT_ID = os.getenv("GRVT_MAINNET_TRADING_ACCOUNT_ID")

    # Validate essential GRVT credentials
    if not GRVT_API_KEY:
        raise ValueError(f"GRVT_API_KEY is not set for {GRVT_ENV} environment. Please check your .env file.")
    if not GRVT_PRIVATE_KEY:
        raise ValueError(f"GRVT_PRIVATE_KEY is not set for {GRVT_ENV} environment. Please check your .env file.")
    if not GRVT_TRADING_ACCOUNT_ID:
        raise ValueError(f"GRVT_TRADING_ACCOUNT_ID is not set for {GRVT_ENV} environment. Please check your .env file.")

    if LIGHTER_ENV == "TESTNET":
        LIGHTER_WALLET_ADDRESS = os.getenv("LIGHTER_TESTNET_WALLET_ADDRESS")
        LIGHTER_PRIVATE_KEY = os.getenv("LIGHTER_TESTNET_PRIVATE_KEY")
        LIGHTER_PUBLIC_KEY = os.getenv("LIGHTER_TESTNET_PUBLIC_KEY")
        LIGHTER_API_KEY_INDEX = int(os.getenv("LIGHTER_TESTNET_API_KEY_INDEX", "2"))
    else:
        LIGHTER_WALLET_ADDRESS = os.getenv("LIGHTER_MAINNET_WALLET_ADDRESS")
        LIGHTER_PRIVATE_KEY = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY")
        LIGHTER_PUBLIC_KEY = os.getenv("LIGHTER_MAINNET_PUBLIC_KEY")
        LIGHTER_API_KEY_INDEX = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "2"))

    LIGHTER_WEB3_RPC_URL = os.getenv("LIGHTER_WEB3_RPC_URL", "https://arb1.arbitrum.io/rpc")

    # Strategy Settings
    DRY_RUN = False # Set to FALSE for actual Testnet testing
    LIGHTER_AMOUNT_SCALAR = 10000 # 0.0001 ETH/BTC unit? specific to Lighter
    SYMBOLS = ["ETH-USDT", "LIT-USDT", "XRP-USDT"] # Multi-symbol support
    SYMBOL_EXCLUDE = ["AI16Z"] # Symbols to exclude from automatic discovery
    SYMBOL = "ETH-USDT" # Legacy/Default support
    ORDER_AMOUNT = 0.001
    PER_TRADE_AMOUNT_USDT = 30.0 # Standard trade size in USD
    MAX_POSITION = 0.1
    SPREAD_BPS = 5 # 0.05%
    HEDGE_SLIPPAGE_BPS = 20 # 0.2%
    LEVERAGE = 10
    
    # Funding Logic
    FUNDING_DIFF_THRESHOLD = 0.0001 # 0.01% difference to trigger
    
    # Dry Run Safety
    MAX_ACTIVE_POSITIONS = 1
    
    # Logging
    LOG_LEVEL = "INFO"
