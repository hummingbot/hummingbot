#!/usr/bin/env python

from typing import (
    Dict,
    List,
    Optional,
)

from decimal import Decimal

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from .msamex_utils import (
    convert_from_exchange_trading_pair,
)


class mSamexOrderBookMessage(OrderBookMessage):
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

        return super(mSamexOrderBookMessage, cls).__new__(
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
        results = [
            OrderBookRow(float(Decimal(ask[0])), float(Decimal(ask[1])), self.update_id) for ask in self.content.get("asks", [])
        ]
        sorted(results, key=lambda a: a.price)
        return results

    @property
    def bids(self) -> List[OrderBookRow]:
        results = [
            OrderBookRow(float(Decimal(bid[0])), float(Decimal(bid[1])), self.update_id) for bid in self.content.get("bids", [])
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

    def __hash__(self) -> int:
        return hash((self.type, self.timestamp, len(self.asks), len(self.bids)))
