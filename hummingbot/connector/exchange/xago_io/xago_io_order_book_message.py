#!/usr/bin/env python

from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.logger import HummingbotLogger


class XagoIoOrderBookMessage(OrderBookMessage):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Optional[float] = None,
        *args,
        **kwargs,
    ):
        
        return super(XagoIoOrderBookMessage, cls).__new__(
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
        elif "instrument_name" in self.content:
            return self.content["instrument_name"]

    @property
    def asks(self) -> List[OrderBookRow]:
        results = []
        if self.content["is_websocket_payload"] == False:
            results = [
                OrderBookRow(float(entry["price"]), float(entry["xrp"]), self.update_id)
                for entry in self.content["asks"]
            ]
        else:
            results = [
                OrderBookRow(entry[0], entry[1], self.update_id)
                for entry in self.content["asks"]
            ]
        return sorted(results, key=lambda a: a.price)

    @property
    def bids(self) -> List[OrderBookRow]:
        results = []
        if self.content["is_websocket_payload"] == False:
            results = [
                OrderBookRow(float(entry["price"]), float(entry["xrp"]), self.update_id)
                for entry in self.content["bids"]
            ]
        else:
            results = [
                OrderBookRow(entry[0], entry[1], self.update_id)
                for entry in self.content["bids"]
            ]
        return sorted(results, key=lambda b: b.price, reverse=True)

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
