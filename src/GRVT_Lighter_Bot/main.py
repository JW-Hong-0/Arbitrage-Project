import sys
import os

# Allow running as script
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Add SDK paths
SDK_ROOT = r"d:\4_Personal_HONG\Python\VIBE_CODING\sdks"
sys.path.append(os.path.join(SDK_ROOT, "grvt-pysdk", "src"))
# Try both potential locations for lighter
sys.path.append(os.path.join(SDK_ROOT, "lighter-python")) 
sys.path.append(os.path.join(SDK_ROOT, "lighter-python", "src"))

import asyncio
import logging
from .strategy import Strategy
from .config import Config

# Setup logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting GRVT-Lighter Bot...")
    strategy = Strategy()
    try:
        await strategy.run()
    except KeyboardInterrupt:
        logger.info("Stopping...")
        await strategy.stop()

if __name__ == "__main__":
    asyncio.run(main())
