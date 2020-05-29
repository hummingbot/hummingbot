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


class BeaxyOrderBookMessage(OrderBookMessage):
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
        return super(BeaxyOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        return int(str(self.content["sequenceNumber"]))

    @property
    def trading_pair(self) -> str:
        return str(self.content.get("security"))

    @property
    def asks(self) -> List[OrderBookRow]:
        return [
            OrderBookRow(float(entry["price"]), float(entry["quantity"]), self.update_id)
            for entry in [x for x in self.content["entries"] if x["side"] == "ASK"]
        ]

    @property
    def bids(self) -> List[OrderBookRow]:
        return [
            OrderBookRow(float(entry["price"]), float(entry["quantity"]), self.update_id)
            for entry in [x for x in self.content["entries"] if x["side"] == "BID"]
        ]
