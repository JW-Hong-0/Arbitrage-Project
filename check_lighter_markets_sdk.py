import asyncio
import sys
import logging
from lighter.api_client import ApiClient
from lighter.configuration import Configuration
from lighter.api.order_api import OrderApi

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        config = Configuration()
        config.host = "https://mainnet.zklighter.elliot.ai"
        
        client = ApiClient(config)
        order_api = OrderApi(client)
        
        print("Fetch Order Book Details (Markets)...")
        # order_book_details usually returns list of all markets info
        details = await order_api.order_book_details()
        
        if details and details.order_book_details:
             print(f"Found {len(details.order_book_details)} markets.")
             
             lit_market = None
             for m in details.order_book_details:
                 # Note: SDK model might not have 'symbol', but usually has 'market_id'.
                 # We need to map ID to symbol? 
                 # Wait, order_book_details returns 'OrderBookDetails' object.
                 # Let's inspect attributes.
                 # Usually: symbol, market_id, min_order_size, etc.
                 # print(dir(m))
                 
                 # Trying to find symbol
                 sym = getattr(m, 'symbol', '')
                 mid = getattr(m, 'market_id', -1)
                 
                 if "LIT" in str(sym).upper():
                     print(f"✅ Found LIT: ID={mid}, Symbol={sym}")
                     lit_market = m
                     break
                 
             if not lit_market:
                 print("LIT Market NOT found. Listing all symbols:")
                 for m in details.order_book_details:
                     print(f"ID: {getattr(m, 'market_id', '?')}, Symbol: {getattr(m, 'symbol', '?')}")
        else:
            print("No details found.")
            
        await client.close()
        
    except Exception as e:
        print(f"SDK Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
