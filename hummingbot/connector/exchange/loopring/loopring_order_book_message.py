#!/usr/bin/env python

import time
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


class LoopringOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = int(time.time())
        return super(LoopringOrderBookMessage, cls).__new__(cls, message_type, content,
                                                            timestamp=timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        if self.type == OrderBookMessageType.SNAPSHOT:
            return self.content["version"]
        elif self.type == OrderBookMessageType.DIFF:
            return self.content["endVersion"]

    @property
    def trade_id(self) -> int:
        return int(self.timestamp)

    @property
    def trading_pair(self) -> str:
        return self.content["topic"]["market"]

    @property
    def asks(self) -> List[OrderBookRow]:
        return self.content["data"]["asks"]

    @property
    def bids(self) -> List[OrderBookRow]:
        return self.content["data"]["bids"]

    @property
    def has_update_id(self) -> bool:
        return True

    @property
    def has_trade_id(self) -> bool:
        return True

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
