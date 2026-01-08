import aiohttp
import asyncio
import json

async def main():
    base_url = "https://mainnet.zklighter.elliot.ai/api/v1"
    headers = {
        "accept": "application/json",
         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        # 1. Inspect Markets for LIT (ID 120) Metadata
        print("=== Fetching Markets Metadata ===")
        async with session.get(f"{base_url}/markets", headers=headers) as resp:
            if resp.status == 200:
                markets = await resp.json()
                lit = next((m for m in markets if m.get('market_id') == 120 or m.get('symbol') == 'LIT-USDT'), None)
                if lit:
                    print(f"✅ LIT Market Found: {json.dumps(lit, indent=2)}")
                else:
                    print("❌ LIT Market NOT found in /markets response.")
            else:
                print(f"Error fetching markets: {resp.status}")

        # 2. Inspect Funding Rates for LIT
        print("\n=== Fetching Funding Rates ===")
        async with session.get(f"{base_url}/funding-rates", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                rates = data.get('funding_rates', [])
                # Filter for LIT (ID 120)
                lit_rates = [r for r in rates if r.get('market_id') == 120]
                eth_rates = [r for r in rates if r.get('market_id') == 0]
                
                print(f"Found {len(lit_rates)} funding entries for LIT.")
                if lit_rates:
                    print("Top 3 LIT Rates:")
                    for r in lit_rates[:3]:
                        print(r)
                
                print(f"\nFound {len(eth_rates)} funding entries for ETH.")
                if eth_rates:
                    print("Top 1 ETH Rate:")
                    print(eth_rates[0])
            else:
                 print(f"Error fetching funding rates: {resp.status}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
