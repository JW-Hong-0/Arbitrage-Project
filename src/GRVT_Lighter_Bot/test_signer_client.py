
import asyncio
import logging
import os
from dotenv import load_dotenv

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Load .env from the script's directory ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(dotenv_path):
    logging.error(f".env file not found at {dotenv_path}. Please create it.")
    exit()
load_dotenv(dotenv_path=dotenv_path)

# --- SDK Imports ---
try:
    from lighter.configuration import Configuration
    from lighter.api_client import ApiClient
    from lighter.api.account_api import AccountApi
    from lighter.signer_client import SignerClient
except ImportError as e:
    logging.error(f"Lighter SDK not found. Please ensure it's installed. Error: {e}")
    exit()

# --- Configurations to Test ---
# We will test both environments to be thorough.
TESTNET_CONFIG = {
    "name": "Lighter Testnet",
    "url": "https://testnet.zklighter.elliot.ai",
    "l1_address": os.getenv("LIGHTER_TESTNET_WALLET_ADDRESS"),
    "private_key": os.getenv("LIGHTER_TESTNET_PRIVATE_KEY"),
    "api_key_index": int(os.getenv("LIGHTER_TESTNET_API_KEY_INDEX", "3")),
}

MAINNET_CONFIG = {
    "name": "Lighter Mainnet",
    "url": "https://mainnet.zklighter.elliot.ai",
    "l1_address": os.getenv("LIGHTER_MAINNET_WALLET_ADDRESS"),
    "private_key": os.getenv("LIGHTER_MAINNET_PRIVATE_KEY"),
    "api_key_index": int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "3")),
}


async def run_final_test(config: dict):
    """
    Performs the definitive test:
    1. Fetches Account Index via L1 Address (read-only).
    2. Attempts to initialize the SignerClient with the found Account Index and the configured API Key.
    """
    name = config["name"]
    url = config["url"]
    l1_address = config["l1_address"]
    private_key = config["private_key"]
    api_key_index = config["api_key_index"]

    logging.info(f"========== FINAL TEST: {name} ==========")

    if not all([url, l1_address, private_key]):
        logging.error(f"SKIPPING: Missing configuration for {name}. Please check your .env file.")
        logging.info(f"========================================\n")
        return

    logging.info(f"L1 Address: {l1_address}")
    logging.info(f"API Key Index: {api_key_index}")

    if api_key_index < 3:
        logging.error(f"FATAL: API Key Index is {api_key_index}, but must be 3 or greater for user-generated keys.")
        logging.info(f"========================================\n")
        return

    account_index = None
    
    # --- Step 1: Fetch Account Index (Read-only) ---
    logging.info(f"[Step 1] Looking up Account Index...")
    try:
        # We use a simple, unauthenticated client for this read-only step.
        sdk_config = Configuration(host=url)
        api_client = ApiClient(sdk_config)
        acc_api = AccountApi(api_client)
        
        # As per user's successful test, use the checksummed address directly.
        resp = await acc_api.account(by="l1_address", value=l1_address)
        
        data = None
        # The user's successful response nests the account in a list
        if hasattr(resp, 'accounts') and isinstance(resp.accounts, list) and resp.accounts:
            data = resp.accounts[0]
        # Fallback for other possible response structures
        elif isinstance(resp, list) and resp:
            data = resp[0]
        else:
            data = resp
        
        if hasattr(data, 'index'):
            account_index = int(data.index)
            logging.info(f"✅ [Step 1] SUCCESS: Found Account Index -> {account_index}")
        else:
            raise ValueError(f"Could not parse 'index' from the account data. Response: {data}")
            
    except Exception as e:
        logging.error(f"❌ [Step 1] FAILED: Could not fetch account data via L1 address. Error: {e}")
        logging.info(f"This means the L1 Address is likely not registered or the URL is wrong.")
        await api_client.close()
        logging.info(f"========================================\n")
        return
    finally:
        if 'api_client' in locals() and api_client:
            await api_client.close()

    # --- Step 2: Initialize SignerClient (Trading Authentication) ---
    logging.info(f"[Step 2] Attempting to initialize Trading Client (SignerClient)...")
    logging.info(f"   - Using Account Index: {account_index}")
    logging.info(f"   - Using API Key Index: {api_key_index}")
    signer_client = None
    try:
        pk = private_key[2:] if private_key.startswith("0x") else private_key
        
        signer_client = SignerClient(
            url=url,
            account_index=account_index,
            # api_key_index is passed as the key in the dictionary below
            api_private_keys={api_key_index: pk}
        )
        # If the line above doesn't raise an exception, the nonce was likely fetched successfully.
        logging.info("✅ [Step 2] SUCCESS: Trading Client (SignerClient) initialized successfully!")
        logging.info("This confirms your API Key has the correct permissions for this account.")

    except Exception as e:
        logging.error(f"❌ [Step 2] FAILED: Could not initialize Trading Client. Error: {e}")
        logging.error("This almost certainly means the provided Private Key and API Key Index are not valid for the discovered Account Index.")
        logging.error("Please generate a NEW API key on the Lighter website for the correct sub-account.")
    
    finally:
        if signer_client and hasattr(signer_client, 'api_client'):
            await signer_client.api_client.close()

    logging.info(f"========================================\n")


async def main():
    logging.info("Starting Lighter API definitive verification...")
    # Test Testnet first
    await run_final_test(TESTNET_CONFIG)
    # Then test Mainnet
    await run_final_test(MAINNET_CONFIG)


if __name__ == "__main__":
    asyncio.run(main())
