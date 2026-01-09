import asyncio
import logging
import os
import sys

# Add project root to path for module resolution
# This allows running the script from the project root (e.g., python src/GRVT_Lighter_Bot/interactive_lighter_trader.py)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.GRVT_Lighter_Bot.exchanges.lighter_api import LighterExchange
from src.GRVT_Lighter_Bot.config import Config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG, # Changed to DEBUG to see detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the interactive Lighter trader."""
    # --- Safety Check ---
    if Config.LIGHTER_ENV != "TESTNET":
        logger.error("="*50)
        logger.error("!!! SAFETY ERROR !!!")
        logger.error("This script is intended for TESTNET ONLY.")
        logger.error(f"Current LIGHTER_ENV: {Config.LIGHTER_ENV}")
        logger.error("Please set LIGHTER_ENV to 'TESTNET' in your .env file to proceed.")
        logger.error("="*50)
        return

    logger.info("Starting Interactive Lighter Trader for TESTNET...")
    
    lighter = LighterExchange()
    await lighter.initialize()
    
    logger.info("Lighter Exchange client initialized.")
    logger.info("Enter 'help' to see available commands.")

    while True:
        try:
            command = await asyncio.to_thread(input, "> ")
            parts = command.strip().lower().split()
            if not parts:
                continue

            action = parts[0]

            if action == 'exit':
                break
            
            elif action == 'help':
                print("\nAvailable commands:")
                print("  leverage <symbol> <leverage> [cross|isolated] - Set leverage (e.g., leverage eth 5)")
                print("  buy <symbol> <amount>                       - Place a market order to open/increase a long position.")
                print("  sell <symbol> <amount>                      - Place a market order to open/increase a short position.")
                print("  close <symbol> <side> <amount>              - Place a reduce-only order to close a position (e.g., close eth sell 0.5)")
                print("  balance                                     - Fetch and display current balance")
                print("  exit                                        - Exit the program")
                print()

            elif action == 'balance':
                balance = await lighter.get_balance()
                logger.info(f"Current Lighter Balance: {balance}")

            elif action == 'leverage':
                if len(parts) < 3:
                    logger.error("Usage: leverage <symbol> <leverage> [cross|isolated]")
                    continue
                symbol = f"{parts[1].upper()}-USDT"
                leverage = int(parts[2])
                margin_mode = 'cross'
                if len(parts) > 3 and parts[3] in ['cross', 'isolated']:
                    margin_mode = parts[3]
                
                logger.info(f"Setting leverage for {symbol} to {leverage}x ({margin_mode})...")
                await lighter.set_leverage(symbol, leverage, margin_mode)

            elif action == 'buy':
                if len(parts) != 3:
                    logger.error("Usage: buy <symbol> <amount>")
                    continue
                symbol = f"{parts[1].upper()}-USDT"
                amount = float(parts[2])
                
                tx_hash = await lighter.place_market_order(symbol, 'buy', amount)
                if tx_hash:
                    logger.info(f"✅ Market buy order submitted successfully. Response: {tx_hash}")
                else:
                    logger.error("❌ Failed to place market buy order.")

            elif action == 'sell':
                if len(parts) != 3:
                    logger.error("Usage: sell <symbol> <amount>")
                    continue
                symbol = f"{parts[1].upper()}-USDT"
                amount = float(parts[2])

                tx_hash = await lighter.place_market_order(symbol, 'sell', amount)
                if tx_hash:
                    logger.info(f"✅ Market sell order submitted successfully. Response: {tx_hash}")
                else:
                    logger.error("❌ Failed to place market sell order.")

            elif action == 'close':
                if len(parts) != 4:
                    logger.error("Usage: close <symbol> <side> <amount> (e.g., close eth sell 0.5 to close a long)")
                    continue
                symbol = f"{parts[1].upper()}-USDT"
                side = parts[2].lower()
                amount = float(parts[3])

                if side not in ['buy', 'sell']:
                    logger.error("Invalid side. Must be 'buy' or 'sell'.")
                    continue

                tx_hash = await lighter.close_market_position(symbol, side, amount)
                if tx_hash:
                    logger.info(f"✅ Close (reduce-only) order submitted successfully. Response: {tx_hash}")
                else:
                    logger.error("❌ Failed to place close order.")
            else:
                logger.warning(f"Unknown command: '{action}'. Type 'help' for options.")

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)

    logger.info("Shutting down...")
    await lighter.close()
    logger.info("Client closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Exiting.")
