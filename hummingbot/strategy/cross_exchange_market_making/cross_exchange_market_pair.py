#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class CrossExchangeMarketPair(NamedTuple):
    """
    Specifies a pair of markets for cross exchange market making.

    e.g. If I want to market make on DDEX WETH-DAI, and hedge on Binance ETHUSDT... then,
         CrossExchangeMarketPair(ddex, "WETH-DAI", "WETH", "DAI",
                          binance, "ETHUSDT", "ETH", "USDT")
    """
    maker: MarketTradingPairTuple
    taker: MarketTradingPairTuple
