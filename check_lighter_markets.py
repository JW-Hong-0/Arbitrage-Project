import aiohttp
import asyncio
import json
from datetime import datetime

async def main():
    # Updated host based on WS success
    base_url = "https://mainnet.zklighter.elliot.ai/api/v1"
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch Markets to find LIT
        headers = {
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        print(f"Fetching Markets from {base_url}...")
        async with session.get(f"{base_url}/markets", headers=headers) as resp:
            if resp.status == 200:
                markets = await resp.json()
                print(f"Found {len(markets)} markets.")
                lit_market = next((m for m in markets if "LIT" in m.get('symbol', '').upper()), None)
                if lit_market:
                    print(f"✅ Found LIT Market: {lit_market}")
                else:
                    print("❌ LIT Market NOT found in list.")
                    # Print all symbols to be sure
                    # print([m.get('symbol') for m in markets])
            else:
                text = await resp.text()
                print(f"Error fetching markets: {resp.status} - {text[:200]}")

        # 2. Fetch Funding Rates to check timestamps
        print("\nFetching Funding Rates...")
        async with session.get(f"{base_url}/funding-rates", headers={"accept": "application/json"}) as resp:
            if resp.status == 200:
                rates = await resp.json()
                data = rates.get('funding_rates', [])
                
                # Check ETH (ID 0) and LIT (if found)
                targets = [m for m in data if m.get('market_id') in [0, lit_market.get('market_id') if lit_market else -1]]
                
                for t in targets:
                    ts = t.get('timestamp') # Is this next or current?
                    dt = datetime.fromtimestamp(ts) if ts else "N/A"
                    print(f"Market {t.get('market_id')}: Rate={t.get('rate')}, Timestamp={ts} ({dt})")
                    
                print(f"Current Local Time: {datetime.now()}")
            else:
                 print(f"Error fetching funding rates: {resp.status}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
