#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.market.market_base import MarketBase
from hummingbot.strategy.market_symbol_pair import MarketSymbolPair


class ArbitrageMarketPair(NamedTuple):
    """
    Specifies a pair of markets for arbitrage
    """
    first: MarketSymbolPair
    second: MarketSymbolPair
