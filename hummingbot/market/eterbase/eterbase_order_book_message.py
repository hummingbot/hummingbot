#!/usr/bin/env python

import pandas as pd
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


class EterbaseOrderBookMessage(OrderBookMessage):
    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Optional[float] = None,
        *args,
        **kwargs,
    ):
        if timestamp is None:
            timestamp = float(content['timestamp'])/1000
        return super(EterbaseOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return int(self.timestamp * 1e3)
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.timestamp * 1e3)
        return -1

    @property
    def trading_pair(self) -> str:
        if "product_id" in self.content:
            return self.content["product_id"]
        elif "symbol" in self.content:
            return self.content["symbol"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("Eterbase order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("Eterbase order book messages have different semantics.")
