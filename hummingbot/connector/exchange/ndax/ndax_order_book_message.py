#!/usr/bin/env python

from collections import namedtuple
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

NdaxOrderBookEntry = namedtuple("NdaxOrderBookEntry", "mdUpdateId accountId actionDateTime actionType lastTradePrice orderId price productPairCode quantity side")
NdaxTradeEntry = namedtuple("NdaxTradeEntry", "tradeId productPairCode quantity price order1 order2 tradeTime direction takerSide blockTrade orderClientId")


class NdaxOrderBookMessage(OrderBookMessage):
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

        return super(NdaxOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            entry: NdaxOrderBookEntry = self.content["data"][0]
            return int(entry.actionDateTime)
        elif self.type == OrderBookMessageType.TRADE:
            entry: NdaxTradeEntry = self.content["data"][0]
            return int(entry.tradeTime)

    @property
    def trade_id(self) -> int:
        entry: NdaxTradeEntry = self.content["data"][0]
        return entry.tradeId

    @property
    def trading_pair(self) -> str:
        return self.content["trading_pair"]

    @property
    def asks(self) -> List[OrderBookRow]:
        entries: List[NdaxOrderBookEntry] = self.content["data"]

        return [
            OrderBookRow(float(entry.price), float(entry.quantity), self.update_id)
            for entry in entries if entry.side == 1
        ]

    @property
    def bids(self) -> List[OrderBookRow]:
        entries: List[NdaxOrderBookEntry] = self.content["data"]

        return [
            OrderBookRow(float(entry.price), float(entry.quantity), self.update_id)
            for entry in entries if entry.side == 0
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
