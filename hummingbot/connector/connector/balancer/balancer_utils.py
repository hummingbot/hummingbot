from typing import List

CENTRALIZED = False
EXAMPLE_PAIR = "WETH-DAI"
DEFAULT_FEES = [0., 0.]

USE_ETHEREUM_WALLET = True
FEE_TYPE = "FlatFee"
FEE_TOKEN = "ETH"

USE_ETH_GAS_LOOKUP = True
GAS_LIMIT = 120000


async def fetch_trading_pairs() -> List[str]:
    return ["WETH-USDC", "WETH-DAI"]
