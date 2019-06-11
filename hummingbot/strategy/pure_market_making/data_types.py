#!/usr/bin/env python

from typing import (
    NamedTuple,
    List
)

from hummingbot.core.event.events import OrderType
from hummingbot.market.market_base import MarketBase

ORDER_PROPOSAL_ACTION_CREATE_ORDERS = 1
ORDER_PROPOSAL_ACTION_CANCEL_ORDERS = 1 << 1


class OrdersProposal(NamedTuple):
    actions: int
    buy_order_type: OrderType
    buy_order_price: List[float]
    buy_order_size: List[float]
    sell_order_type: OrderType
    sell_order_price: List[float]
    sell_order_size: List[float]
    cancel_order_ids: List[str]


class PricingProposal(NamedTuple):
    buy_order_price: List[float]
    sell_order_price: List[float]


class SizingProposal(NamedTuple):
    buy_order_size: List[float]
    sell_order_size: List[float]


class MarketInfo(NamedTuple):
    market: MarketBase
    symbol: str
    base_currency: str
    quote_currency: str
