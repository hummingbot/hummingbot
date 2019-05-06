#!/usr/bin/env python

from typing import (
    NamedTuple,
    Awaitable
)
import pandas as pd
from wings.market.market_base import MarketBase


class DiscoveryMarketPair(NamedTuple):
    """
    Specifies a pair of markets for discovery
    """
    market_1: MarketBase
    market_1_fetch_market_info: Awaitable[pd.DataFrame]
    market_2: MarketBase
    market_2_fetch_market_info: Awaitable[pd.DataFrame]
