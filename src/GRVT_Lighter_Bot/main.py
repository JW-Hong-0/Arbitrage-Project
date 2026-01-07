import sys
import os

# Allow running as script
if __name__ == "__main__":
    # This path adjustment is crucial for running as a module from the project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.append(project_root)

import asyncio
import logging
import sys
from datetime import datetime
from src.GRVT_Lighter_Bot.strategy import Strategy
from src.GRVT_Lighter_Bot.config import Config

# Setup logging to both file and console
log_filename = f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, "INFO"),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    logger.info(f"Logging to file: {log_filename}")
    logger.info("Starting GRVT-Lighter Bot...")
    strategy = Strategy()
    try:
        # The run method now contains the initialization logic
        await strategy.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping...")
    except Exception as e:
        logger.error(f"An unexpected error occurred in main: {e}", exc_info=True)
    finally:
        logger.info("Shutting down strategy...")
        await strategy.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # To catch errors during asyncio.run itself
        print(f"Failed to run asyncio event loop: {e}")