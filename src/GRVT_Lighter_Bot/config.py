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
    SYMBOLS = ["ETH-USDT", "LIT-USDT"] # Multi-symbol support
    SYMBOL = "ETH-USDT" # Legacy/Default support
    ORDER_AMOUNT = 0.001
    MAX_POSITION = 0.1
    SPREAD_BPS = 5 # 0.05%
    HEDGE_SLIPPAGE_BPS = 20 # 0.2%
    LEVERAGE = 10
    
    # Funding Logic
    FUNDING_DIFF_THRESHOLD = 0.0001 # 0.01% difference to trigger
    
    # Logging
    LOG_LEVEL = "INFO"
