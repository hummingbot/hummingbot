#!/usr/bin/env python

from typing import NamedTuple

from wings.market.market_base import MarketBase


class PureMarketPair(NamedTuple):
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
    price: float
    total_size_commited: float = 0
    order_size: float = 0
    adjust_order_time: float = 15
    #volatility: float = 0.2
    #risk_aversion: float = 0.1
    distance_from_mid: float = 0.05




