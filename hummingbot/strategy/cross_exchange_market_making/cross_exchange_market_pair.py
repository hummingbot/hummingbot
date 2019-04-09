#!/usr/bin/env python

from typing import NamedTuple

from wings.market_base import MarketBase


class CrossExchangeMarketPair(NamedTuple):
    """
    Specifies a pair of markets for cross exchange market making.

    e.g. If I want to market make on DDEX WETH-DAI, and hedge on Binance ETHUSDT... then,
         CrossExchangeMarketPair(ddex, "WETH-DAI", "WETH", "DAI",
                          binance, "ETHUSDT", "ETH", "USDT")
    """
    maker_market: MarketBase
    maker_symbol: str
    maker_base_currency: str
    maker_quote_currency: str
    taker_market: MarketBase
    taker_symbol: str
    taker_base_currency: str
    taker_quote_currency: str
    top_depth_tolerance: float = 0
