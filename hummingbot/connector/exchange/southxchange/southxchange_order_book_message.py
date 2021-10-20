#!/usr/bin/env python

from typing import (
    Dict,
    List,
    Optional,
)

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)


class SouthXchangeOrderBookMessage(OrderBookMessage):
    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],        
        *args,
        **kwargs,
    ):
        # if timestamp is None:
        #     if message_type is OrderBookMessageType.SNAPSHOT:
        #         raise ValueError("timestamp must not be None when initializing snapshot messages.")
        #     timestamp = content["timestamp"]

        return super(SouthXchangeOrderBookMessage, cls).__new__(
            cls, message_type, content, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return int(self.timestamp)
        return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.timestamp)
        return -1

    @property
    def trading_pair(self) -> str:
        return self.content["trading_pair"]

    @property
    def asks(self) -> List[OrderBookRow]:
        results = [
            OrderBookRow(float(ask.get("Price")), float(ask.get("Amount")), self.update_id) for ask in self.content["SellOrders"]
        ]
        sorted(results, key=lambda a: a.price)
        return results

    @property
    def bids(self) -> List[OrderBookRow]:
        results = [
            OrderBookRow(float(bid.get("Price")), float(bid.get("Amount")), self.update_id) for bid in self.content["BuyOrders"]
        ]
        sorted(results, key=lambda a: a.price)
        return results

    def __eq__(self, other) -> bool:
        return self.type == other.type and self.timestamp == other.timestamp

    def __lt__(self, other) -> bool:
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        else:
            """
            If timestamp is the same, the ordering is snapshot < diff < trade
            """
            return self.type.value < other.type.value
