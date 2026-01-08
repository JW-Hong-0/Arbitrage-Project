import asyncio
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
        
        print("=== Fetching Markets via SDK ===")
        details = await order_api.order_book_details()
        
        if details and details.order_book_details:
             markets = details.order_book_details
             lit = next((m for m in markets if getattr(m, 'market_id', -1) == 120), None)
             
             if lit:
                 print(f"✅ LIT Market Found:")
                 print(f"  Symbol: {getattr(lit, 'symbol', 'N/A')}")
                 print(f"  Market ID: {getattr(lit, 'market_id', 'N/A')}")
                 print(f"  Min Order Size: {getattr(lit, 'min_order_size', 'N/A')}")
                 print(f"  Max Leverage: {getattr(lit, 'max_leverage', 'N/A')}")
                 print(f"  Tick Size: {getattr(lit, 'tick_size', 'N/A')}")
             else:
                 print("❌ LIT Market (ID 120) NOT found in SDK response.")
        else:
            print("No details found.")
            
        await client.close()
        
    except Exception as e:
        print(f"SDK Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
