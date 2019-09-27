#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class ArbitrageMarketPair(NamedTuple):
    """
    Specifies a pair of markets for arbitrage
    """
    first: MarketTradingPairTuple
    second: MarketTradingPairTuple
