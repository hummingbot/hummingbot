#!/usr/bin/env python

from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class BitmartOrderBookMessage(OrderBookMessage):
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

        return super(BitmartOrderBookMessage, cls).__new__(
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

    @property
    def asks(self) -> List[OrderBookRow]:
        if "sells" in self.content:
            results = [
                OrderBookRow(float(ask["price"]), float(ask["amount"]), self.update_id) for ask in self.content["sells"]
            ]
        elif "asks" in self.content:
            results = [
                OrderBookRow(float(ask[0]), float(ask[1]), self.update_id) for ask in self.content["asks"]
            ]
        sorted(results, key=lambda a: a.price)
        return results

    @property
    def bids(self) -> List[OrderBookRow]:
        if "buys" in self.content:
            results = [
                OrderBookRow(float(bid["price"]), float(bid["amount"]), self.update_id) for bid in self.content["buys"]
            ]
        elif "bids" in self.content:
            results = [
                OrderBookRow(float(bid[0]), float(bid[1]), self.update_id) for bid in self.content["bids"]
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
        return hash((self.type, self.timestamp))
