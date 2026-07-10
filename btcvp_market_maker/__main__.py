"""Allow running as: python -m btcvp_market_maker"""

import asyncio

from .main import main

if __name__ == "__main__":
    asyncio.run(main())
