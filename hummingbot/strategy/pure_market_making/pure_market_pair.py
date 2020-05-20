#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.market.market_base import MarketBase


class PureMarketPair(NamedTuple):
    """
    Specifies a pair of markets for pure market making.

    e.g. If I want to market make on Binance ETH-USDT, then,
         PureMarketPair(binance, "ETHUSDT", "ETH", "USDT")
    """
    maker_market: MarketBase
    maker_trading_pair: str
    maker_base_currency: str
    maker_quote_currency: str
