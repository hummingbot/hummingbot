from typing import List

CENTRALIZED = False
EXAMPLE_PAIR = "TERRA-USDT"
DEFAULT_FEES = [0., 0.]


async def fetch_trading_pairs() -> List[str]:
    # Todo: find all available trading pairs
    return ["TERRA-USDT"]
