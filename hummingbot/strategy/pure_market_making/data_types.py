#!/usr/bin/env python

from typing import NamedTuple

from hummingbot.core.event.events import OrderType
from hummingbot.market.market_base import MarketBase


class OrdersProposal(NamedTuple):
    buy_order_type: OrderType
    buy_order_price: float
    buy_order_size: float
    sell_order_type: OrderType
    sell_order_price: float
    sell_order_size: float


class PricingProposal(NamedTuple):
    buy_order_price: float
    sell_order_price: float


class SizingProposal(NamedTuple):
    buy_order_size: float
    sell_order_size: float


class MarketInfo(NamedTuple):
    market: MarketBase
    symbol: str
    base_currency: str
    quote_currency: str
