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
from .altmarkets_utils import (
    convert_from_exchange_trading_pair,
)


class AltmarketsOrderBookMessage(OrderBookMessage):
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
            timestamp = content["date"]

        return super(AltmarketsOrderBookMessage, cls).__new__(
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
            return self.content['trade_id']
        return -1

    @property
    def trading_pair(self) -> str:
        if "trading_pair" in self.content:
            return self.content["trading_pair"]
        elif "market" in self.content:
            return convert_from_exchange_trading_pair(self.content["market"])

    @property
    def asks(self) -> List[OrderBookRow]:
        asks = map(self.content.get("asks", []), lambda ask: {"price": ask[0], "size": ask[1]})

        return [
            OrderBookRow(float(price), float(amount), self.update_id) for price, amount in asks
        ]

    @property
    def bids(self) -> List[OrderBookRow]:
        bids = map(self.content.get("bids", []), lambda bid: {"price": bid[0], "size": bid[1]})

        return [
            OrderBookRow(float(price), float(amount), self.update_id) for price, amount in bids
        ]

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
