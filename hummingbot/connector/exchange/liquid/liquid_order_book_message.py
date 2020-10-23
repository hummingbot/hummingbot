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


class LiquidOrderBookMessage(OrderBookMessage):
    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Optional[float] = None,
        *args,
        **kwargs,
    ):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = content["time"] * 1e-3
        return super(LiquidOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trading_pair(self) -> (str):
        return self.content.get('trading_pair', None)

    @property
    def asks(self) -> (List[OrderBookRow]):
        return [
            OrderBookRow(float(price), float(amount), self.update_id)
            for price, amount, *trash in self.content.get("asks", [])
        ]

    @property
    def bids(self) -> (List[OrderBookRow]):
        return [
            OrderBookRow(float(price), float(amount), self.update_id)
            for price, amount, *trash in self.content.get("bids", [])
        ]
