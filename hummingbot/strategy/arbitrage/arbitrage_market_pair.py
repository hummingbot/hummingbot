#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.market.market_base import MarketBase


class ArbitrageMarketPair(NamedTuple):
    """
    Specifies a pair of markets for arbitrage
    """
    market_1: MarketBase
    market_1_trading_pair: str
    market_1_base_asset: str
    market_1_quote_asset: str
    market_2: MarketBase
    market_2_trading_pair: str
    market_2_base_asset: str
    market_2_quote_asset: str
