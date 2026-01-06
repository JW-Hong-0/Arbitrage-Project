import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # GRVT Settings
    GRVT_API_KEY = os.getenv("GRVT_API_KEY", "")
    GRVT_PRIVATE_KEY = os.getenv("GRVT_SECRET_KEY", "") # User calls it SECRET_KEY
    GRVT_TRADING_ACCOUNT_ID = os.getenv("GRVT_TRADING_ACCOUNT_ID", "0")
    GRVT_TRADING_ADDRESS = os.getenv("GRVT_TRADING_Address", "")
    GRVT_ENV = os.getenv("GRVT_ENV", "TESTNET")  # Keep this for SDK selection

    # Lighter Settings
    LIGHTER_WALLET_ADDRESS = os.getenv("LIGHTER_WALLET_ADDRESS", "")
    LIGHTER_PRIVATE_KEY = os.getenv("LIGHTER_PRIVATE_KEY", "")
    LIGHTER_PUBLIC_KEY = os.getenv("LIGHTER_PUBLIC_KEY", "")
    LIGHTER_WEB3_RPC_URL = os.getenv("LIGHTER_WEB3_RPC_URL", "https://arb1.arbitrum.io/rpc")

    # Strategy Settings
    SYMBOL = "BTC-USDT" # Valid symbol for both (mapped internally)
    ORDER_AMOUNT = 0.001
    MAX_POSITION = 0.1
    SPREAD_BPS = 5 # 0.05%
    HEDGE_SLIPPAGE_BPS = 20 # 0.2%
    LEVERAGE = 10
    
    # Funding Logic
    FUNDING_DIFF_THRESHOLD = 0.0001 # 0.01% difference to trigger
    
    # Logging
    LOG_LEVEL = "INFO"
