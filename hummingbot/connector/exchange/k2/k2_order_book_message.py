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


class K2OrderBookMessage(OrderBookMessage):
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
            timestamp = content["timestamp"]

        return super(K2OrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return int(self.timestamp)
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.timestamp)
        return -1

    @property
    def trading_pair(self) -> str:
        if "trading_pair" in self.content:
            return self.content["trading_pair"]
        elif "symbol" in self.content:
            return self.content["symbol"]
        elif "pair" in self.content:
            return self.content["pair"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("K2 order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("K2 order book messages have different semantics.")

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
