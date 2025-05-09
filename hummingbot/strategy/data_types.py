from dataclasses import dataclass
from decimal import Decimal
from typing import List, NamedTuple

from hummingbot.core.data_type.common import OrderType

ORDER_PROPOSAL_ACTION_CREATE_ORDERS = 1
ORDER_PROPOSAL_ACTION_CANCEL_ORDERS = 1 << 1

NaN = float("nan")


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


@dataclass(frozen=True)
class HangingOrder:
    order_id: str
    trading_pair: str
    is_buy: bool
    price: Decimal
    amount: Decimal
    creation_timestamp: float

    @property
    def base_asset(self):
        return self.trading_pair.split('-')[0]

    @property
    def quote_asset(self):
        return self.trading_pair.split('-')[1]

    def distance_to_price(self, price: Decimal):
        return abs(self.price - price)

    def __eq__(self, other):
        return isinstance(other, HangingOrder) and all(
            (self.trading_pair == other.trading_pair,
             self.is_buy == other.is_buy,
             self.price == other.price,
             self.amount == other.amount))

    def __hash__(self):
        return hash((self.trading_pair, self.is_buy, self.price, self.amount))
