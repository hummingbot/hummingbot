#!/usr/bin/env python

from typing import Dict, List, Optional

import pandas as pd

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class CoinbaseProOrderBookMessage(OrderBookMessage):
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
            timestamp = pd.Timestamp(content["time"], tz="UTC").timestamp()
        return super(CoinbaseProOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return int(self.content["sequence"])
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.content["sequence"])
        return -1

    @property
    def trading_pair(self) -> str:
        if "product_id" in self.content:
            return self.content["product_id"]
        elif "symbol" in self.content:
            return self.content["symbol"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("Coinbase Pro order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("Coinbase Pro order book messages have different semantics.")
