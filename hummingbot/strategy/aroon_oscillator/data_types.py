#!/usr/bin/env python
from typing import (
    NamedTuple,
    List
)
from decimal import Decimal
from hummingbot.core.event.events import OrderType

ORDER_PROPOSAL_ACTION_CREATE_ORDERS = 1
ORDER_PROPOSAL_ACTION_CANCEL_ORDERS = 1 << 1


class OrdersProposal(NamedTuple):
    actions: int
    buy_order_type: OrderType
    buy_order_prices: List[Decimal]
    buy_order_sizes: List[Decimal]
    sell_order_type: OrderType
    sell_order_prices: List[Decimal]
    sell_order_sizes: List[Decimal]
    cancel_order_ids: List[str]


class PricingProposal(NamedTuple):
    buy_order_prices: List[Decimal]
    sell_order_prices: List[Decimal]


class SizingProposal(NamedTuple):
    buy_order_sizes: List[Decimal]
    sell_order_sizes: List[Decimal]


class InventorySkewBidAskRatios(NamedTuple):
    bid_ratio: float
    ask_ratio: float


class PriceSize:
    def __init__(self, price: Decimal, size: Decimal):
        self.price: Decimal = price
        self.size: Decimal = size

    def __repr__(self):
        return f"[ p: {self.price} s: {self.size} ]"


class Proposal:
    def __init__(self, buys: List[PriceSize], sells: List[PriceSize]):
        self.buys: List[PriceSize] = buys
        self.sells: List[PriceSize] = sells

    def __repr__(self):
        return f"{len(self.buys)} buys: {', '.join([str(o) for o in self.buys])} " \
               f"{len(self.sells)} sells: {', '.join([str(o) for o in self.sells])}"
