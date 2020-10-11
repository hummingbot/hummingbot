from typing import List

CENTRALIZED = False
EXAMPLE_PAIR = "ETH-USDC"
DEFAULT_FEES = [0., 0.]


async def fetch_trading_pairs() -> List[str]:
    return ["WETH-USDC", "WETH-DAI"]
