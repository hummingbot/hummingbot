#!/usr/bin/env python

from typing import NamedTuple

from wings.market.market_base import MarketBase


class ArbitrageMarketPair(NamedTuple):
    """
    Specifies a pair of markets for arbitrage
    """
    market_1: MarketBase
    market_1_symbol: str
    market_1_base_currency: str
    market_1_quote_currency: str
    market_2: MarketBase
    market_2_symbol: str
    market_2_base_currency: str
    market_2_quote_currency: str
