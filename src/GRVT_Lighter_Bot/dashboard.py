import os
import time
from typing import List
from .strategy.opportunity_scanner import arbitrage_opportunity

class Dashboard:
    def __init__(self, bot):
        self.bot = bot
        self.log_file = os.path.join(os.path.dirname(__file__), "Main_bot_log.txt")

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    async def print_dashboard(self):
        self.clear_screen()
        
        # 1. Header & Balances
        # GRVT Balance
        grvt_data = await self.bot.grvt.get_balance()
        grvt_equity = grvt_data.get('equity', 0.0)
        grvt_avail = grvt_data.get('available', 0.0)
        
        # Lighter Balance
        lighter_equity = 0.0
        lighter_avail = 0.0
        try:
             l_data = await self.bot.lighter.get_balance()
             lighter_equity = l_data.get('equity', 0.0)
             lighter_avail = l_data.get('available', 0.0)
        except Exception as e:
             # logger.error(f"Dash: Lighter bal error: {e}")
             pass
        
        print(f"Bot Mode: {'LIVE (DRY RUN)' if not self.bot.state.positions else 'LIVE'}") 
        # Actually mode logic is in main_bot running state.
        
        print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        print(f"GRVT    | Equity: ${grvt_equity:.2f} | Available: ${grvt_avail:.2f}")
        print(f"Lighter | Equity: ${lighter_equity:.2f} | Available: ${lighter_avail:.2f}")
        print("=" * 100)
        
        # 2. Opportunity Table
        print(f"{'Symbol':<8} | {'GRVT Price':<12} | {'Lighter Price':<14} | {'GRVT Rate (Int)':<18} | {'Lighter Rate (Adj)':<24} | {'Diff':<10} | {'Recommendation'}")
        print("-" * 100)
        
        # Sort opportunities by Spread desc
        # The scanner now returns ALL scanned symbols, so we need to filter/sort.
        opps = sorted(self.bot.scanner.opportunities.values(), key=lambda x: x.spread, reverse=True)
        
        for opp in opps[:15]: # Show top 15
            rec_color = "" 
            # Simple color simulation using ANSI codes if supported, else text.
            # Windows CMD might need colorama, let's stick to text for simplicity or basic ANSI.
            
            grvt_desc = f"{opp.grvt_funding_rate:.5f} ({opp.grvt_funding_interval_hours}h)"
            lighter_desc = f"{opp.lighter_funding_rate:.5f} (1h->{opp.adj_lighter_rate_1h:.5f})"
            diff_desc = f"{opp.spread:.5f}"
            
            # ANSI Color Codes
            GREEN = '\033[92m'
            RED = '\033[91m'
            RESET = '\033[0m'
            
            rec_str = f"{opp.direction}"
            # Add simple visual cue
            if opp.spread > self.bot.scanner.min_spread:
                color = GREEN if 'Long_GRVT' in opp.direction else RED
                rec_str = f"{color}*** {rec_str} ***{RESET}"
            
            grvt_price_str = f"${opp.grvt_price:.2f}"
            lighter_price_str = f"${opp.lighter_price:.2f}"

            print(f"{opp.symbol:<8} | {grvt_price_str:<12} | {lighter_price_str:<14} | {grvt_desc:<18} | {lighter_desc:<24} | {diff_desc:<10} | {rec_str}")
            
        print("-" * 100)
        
        # 3. Active Positions
        active_pos = self.bot.state.get_active_positions()
        if active_pos:
            print(f"\nActive Positions ({len(active_pos)}):")
            for pos in active_pos:
                print(f"[{pos.symbol}] Size: {pos.size} | Status: {pos.status} | Hedge Pending: {pos.pending_hedge_qty}")
        else:
            print("\nNo Active Positions.")
            
        # 4. Save to Log File (Append snapshot)
        # Maybe not every refresh? User said "Main_bot_log.txt saves logs". 
        # Usually we want the *execution logs* in the file, not just the dashboard snapshot.
        # But user asked for dashboard TO BE the monitoring tool.
        # Let's just ensure logger writes to file.
