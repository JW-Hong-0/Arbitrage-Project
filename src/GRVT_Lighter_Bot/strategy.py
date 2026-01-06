import asyncio
import logging
from .config import Config
from .exchanges.grvt_api import GrvtExchange
from .exchanges.lighter_api import LighterExchange

logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self):
        self.grvt = GrvtExchange()
        self.lighter = LighterExchange()
        self.running = False

    async def run(self):
        self.running = True
        logger.info("Strategy started.")
        
        # Start fill listener task
        asyncio.create_task(self.grvt.listen_fills(self.on_fill))
        
        # Main Loop: Scan -> Dashboard -> Wait
        while self.running:
            try:
                best_opportunity = await self.scan_market()
                self.print_dashboard(best_opportunity)
                
                if best_opportunity:
                    # Execute logic if good enough
                    # For now, just logging
                    pass
                    
            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
            
            await asyncio.sleep(5) # Fast update for dashboard

    async def scan_market(self):
        """
        Scan all tickers to find the best Funding Rate difference.
        Returns dict with details of the best pair.
        """
        grvt_tickers = await self.grvt.get_all_tickers()
        lighter_rates = await self.lighter.get_all_tickers()
        
        # We need to map Lighter symbols to GRVT symbols
        # This mapping depends on exact string format response from APIs
        # Placeholder mapping logic:
        # Assuming common pairs exist in both
        
        opportunities = []
        
        # Iterate and compare (Mock logic for structure)
        # Real logic requires parsing the ticker objects deeply
        
        return None # Return best opportunity dict

    def print_dashboard(self, opportunity):
        # Clear screen/Print status
        # In Docker/CI clearing might be messy, so just print separator
        print("\n" + "="*30)
        print(f"GRVT-Lighter Bot | Status: Running")
        print(f"Time: {asyncio.get_event_loop().time()}")
        if opportunity:
            print(f"Best Opportunity: {opportunity}")
        else:
            print("No significant opportunity found or scanning...")
        print("="*30 + "\n")

    async def on_fill(self, fill_data):
        logger.info(f"Fill received: {fill_data}")
        # Hedge logic
        # await self.lighter.place_market_order(...)
        pass
        
    async def stop(self):
        self.running = False
        await self.lighter.close()
