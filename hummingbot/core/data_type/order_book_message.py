#!/usr/bin/env python

from collections import namedtuple
from enum import Enum
from functools import total_ordering
from typing import (
    Dict,
    List,
    Optional,
)

from hummingbot.core.data_type.order_book_row import OrderBookRow


class OrderBookMessageType(Enum):
    SNAPSHOT = 1
    DIFF = 2
    TRADE = 3


@total_ordering
class OrderBookMessage(namedtuple("_OrderBookMessage", "type, content, timestamp")):
    type: OrderBookMessageType
    content: Dict[str, any]
    timestamp: float

    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Optional[float] = None,
        *args,
        **kwargs,
    ):
        return super(OrderBookMessage, cls).__new__(cls, message_type, content, timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return self.content["update_id"]
        else:
            return -1

    @property
    def first_update_id(self) -> int:
        if self.type is OrderBookMessageType.DIFF:
            return self.content.get("first_update_id", self.update_id)
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return self.content["trade_id"]
        return -1

    @property
    def trading_pair(self) -> str:
        return self.content["trading_pair"]

    @property
    def asks(self) -> List[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(amount), self.update_id) for price, amount, *trash in self.content["asks"]
        ]

    @property
    def bids(self) -> List[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(amount), self.update_id) for price, amount, *trash in self.content["bids"]
        ]

    @property
    def has_update_id(self) -> bool:
        return self.type in {OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT}

    @property
    def has_trade_id(self) -> bool:
        return self.type == OrderBookMessageType.TRADE

    def __eq__(self, other: "OrderBookMessage") -> bool:
        if self.has_update_id and other.has_update_id:
            return self.update_id == other.update_id
        elif self.has_trade_id and other.has_trade_id:
            return self.trade_id == other.trade_id
        else:
            return False

    def __lt__(self, other: "OrderBookMessage") -> bool:
        if self.has_update_id and other.has_update_id:
            return self.update_id < other.update_id
        elif self.has_trade_id and other.has_trade_id:
            return self.trade_id < other.trade_id
        else:
            if self.timestamp != other.timestamp:
                return self.timestamp < other.timestamp
            else:
                # For messages of same timestamp, order book messages come before trade messages.
                return self.has_update_id
