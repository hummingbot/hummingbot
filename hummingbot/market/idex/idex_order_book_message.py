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


class IDEXOrderBookMessage(OrderBookMessage):
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
                timestamp = 0.0
            else:
                datetime_str: str = content.get("updatedAt") or content.get("createdAt")
                if datetime_str is None:
                    raise ValueError(f"Invalid time for this diff message: {content}")
                timestamp = pd.Timestamp(datetime_str, tz="UTC").timestamp()
        return super(IDEXOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trading_pair(self) -> str:
        return self.content["market"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("IDEX order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("IDEX order book messages have different semantics.")

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

    def __lt__(self, other) -> bool:
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        else:
            """
            If timestamp is the same, the ordering is snapshot < diff < trade
            """
            return self.type.value < other.type.value
