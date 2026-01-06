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
                # 1. Asset Check
                grvt_bal = await self.grvt.get_balance()
                lighter_bal = await self.lighter.get_balance()
                
                # 2. Market Scan
                best_opportunity = await self.scan_market()
                
                # 3. Print Dashboard
                self.print_dashboard(best_opportunity, grvt_bal, lighter_bal)
                
                # 4. Exit Check (Closing positions if spread unfavorable)
                await self.check_exit_conditions(grvt_bal, lighter_bal, best_opportunity)

                # 5. Entry Logic
                if best_opportunity:
                    action = best_opportunity['action']
                    symbol = best_opportunity['symbol']
                    
                    trade_side = 'sell' if best_opportunity['grvt_rate'] > best_opportunity['lighter_rate'] else 'buy'
                    
                    # Risk Check: Max Position
                    # TODO: Sum up actual position sizes from bal
                    
                    # logger.info(f"Opportunity found! Action: {trade_side.upper()} GRVT (Maker) -> {('BUY' if trade_side=='sell' else 'SELL')} Lighter (Taker)")
                    
                    if Config.DRY_RUN:
                        logger.info(f"[DRY RUN] Placing Limit Order on GRVT: {trade_side} {Config.ORDER_AMOUNT} @ Current Price")
                        # Simulate Fill after delay
                        asyncio.create_task(self.simulate_fill(symbol, trade_side, Config.ORDER_AMOUNT))
                    else:
                        # Fetch price first and place order
                        pass

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
            
            await asyncio.sleep(5) # Fast update for dashboard

    async def check_exit_conditions(self, grvt_bal, lighter_bal, opportunity):
        """
        Check if we need to close positions.
        """
        # Logic: If spread drops below 0 or negative, close positions.
        # For Phase 1, we primarily just monitor.
        # Implementation:
        # 1. Identify paired positions (Long GRVT + Short Lighter)
        # 2. Check current spread
        # 3. If spread < EXIT_THRESHOLD, trigger close.
        pass

    async def scan_market(self):
        """
        Scan all tickers to find the best Funding Rate difference.
        Returns dict with details of the best pair.
        """
        try:
            # 1. Fetch GRVT Data
            # Use Constant Map if needed, but for now Config.SYMBOL is sufficient
            grvt_rate = await self.grvt.get_funding_rate(Config.SYMBOL)
            
            # 2. Fetch Lighter Data
            lighter_rates = await self.lighter.get_all_tickers()
            
            # Find Lighter rate for Config.SYMBOL
            lighter_rate_val = None
            
            # Parsing Lighter SDK response
            # Assuming lighter_rates is a list of objects or dicts.
            if isinstance(lighter_rates, list):
                for r in lighter_rates:
                    # check attributes .symbol or ['symbol']
                    sym = getattr(r, 'symbol', r.get('symbol') if isinstance(r, dict) else None)
                    # Normalize symbol check using simple string matching or utils
                    if sym and (Config.SYMBOL in sym): 
                        lighter_rate_val = float(getattr(r, 'rate_daily', 0) or r.get('rate_daily', 0)) # Verify unit
                        break

            # MOCK DATA for Dry Run
            if Config.DRY_RUN:
                if grvt_rate is None: grvt_rate = 0.0001
                if lighter_rate_val is None: lighter_rate_val = 0.0005 
            
            if grvt_rate is not None and lighter_rate_val is not None:
                diff = abs(grvt_rate - lighter_rate_val)
                # logger.info(f"Scan: GRVT={grvt_rate:.6f} Lighter={lighter_rate_val:.6f} Diff={diff:.6f}")
                
                if diff > Config.FUNDING_DIFF_THRESHOLD:
                    return {
                        "symbol": Config.SYMBOL,
                        "grvt_rate": grvt_rate,
                        "lighter_rate": lighter_rate_val,
                        "diff": diff,
                        "action": "OPEN" 
                    }
                    
        except Exception as e:
            logger.error(f"Scan Market Error: {e}")
            
        return None

    def print_dashboard(self, opportunity, grvt_bal, lighter_bal):
        # Clear screen/Print status
        print("\n" + "="*50)
        print(f"GRVT-Lighter Bot | Mode: {'DRY RUN' if Config.DRY_RUN else 'LIVE'}")
        print(f"Time: {asyncio.get_event_loop().time():.2f}")
        
        print("-" * 20 + " ASSETS " + "-" * 20)
        print(f"GRVT    | Equity: ${grvt_bal.get('equity', 0):.2f} | Free: ${grvt_bal.get('available', 0):.2f}")
        print(f"Lighter | Equity: ${lighter_bal.get('equity', 0):.2f} | Free: ${lighter_bal.get('available', 0):.2f}")
        
        print("-" * 20 + " POSITIONS " + "-" * 20)
        all_pos = grvt_bal.get('positions', []) + lighter_bal.get('positions', [])
        if not all_pos:
            print("No active positions.")
        else:
            for p in all_pos:
                print(f"{p.get('symbol')} {p.get('side')} {p.get('size')} @ {p.get('entry_price')}")

        print("-" * 20 + " STRATEGY " + "-" * 20)
        if opportunity:
            print(f"Opportunity: {opportunity['symbol']}")
            print(f"   GRVT Rate: {opportunity['grvt_rate']:.6f}")
            print(f"   Lighter Rate: {opportunity['lighter_rate']:.6f}")
            print(f"   Diff: {opportunity['diff']:.6f}")
        else:
            print("Scanning for opportunities...")
        print("="*50 + "\n")

    async def on_fill(self, fill_data):
        logger.info(f"Fill received: {fill_data}")
        
        # Hedge logic
        try:
            # Parse fill data
            # Standardizing input: fill_data should be a dict
            if isinstance(fill_data, str):
                import json
                try: fill_data = json.loads(fill_data)
                except: pass
            
            # Check structure (assuming pysdk format or raw dict)
            # If fill_data is from 'user.trades', it might be a list of trades or single named tuple
            
            # Using defaults for robustness during initial dev
            symbol = Config.SYMBOL 
            side = 'buy'
            amount = Config.ORDER_AMOUNT
            
            # Try to extract real values if possible
            if isinstance(fill_data, dict):
                symbol = fill_data.get('instrument', symbol).split('_')[0]
                side = fill_data.get('side', side)
                amount = float(fill_data.get('size', fill_data.get('amount', amount)))
            
            # Opposite side for hedging
            hedge_side = 'sell' if side.lower() == 'buy' else 'buy'
            
            logger.info(f"Hedging: {hedge_side.upper()} {amount} {symbol} on Lighter")
            
            if Config.DRY_RUN:
                await self.lighter.place_market_order(symbol, hedge_side, amount)
            else:
                 await self.lighter.place_market_order(symbol, hedge_side, amount)
                 
        except Exception as e:
            logger.error(f"Error during hedging: {e}")

    async def simulate_fill(self, symbol, side, amount):
        """Helper to simulate WS fill event in Dry Run"""
        await asyncio.sleep(2)
        mock_fill = {
            "instrument": f"{symbol}_USDT_Perp",
            "side": side,
            "size": amount,
            "price": 95000.0,
            "type": "fill"
        }
        logger.info(f"[DRY RUN] Simulating Fill Event...")
        await self.on_fill(mock_fill)

    async def stop(self):
        self.running = False
        await self.lighter.close()
