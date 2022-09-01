#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class MakerTakerMarketPair(NamedTuple):
    """
    Specifies a pair of maker and taker markets

    e.g. If I want to market make on DDEX WETH-DAI, and hedge on Binance ETHUSDT... then,
         MakerTakerMarketPair(ddex, "WETH-DAI", "WETH", "DAI",
                          binance, "ETHUSDT", "ETH", "USDT")
    """
    maker: MarketTradingPairTuple
    taker: MarketTradingPairTuple
