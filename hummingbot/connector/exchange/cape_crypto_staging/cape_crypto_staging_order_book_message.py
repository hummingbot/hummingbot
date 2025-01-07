from collections import namedtuple
from enum import Enum
from functools import total_ordering
from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


@total_ordering
class CapeCryptoStagingOrderBookBookMessage(namedtuple("_OrderBookMessage", "type, content, timestamp")):
    type: OrderBookMessageType
    content: Dict[str, any]
    timestamp: float

    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Optional[float] = None,
        *args,
        **kwargs,
    ):
        return super(CapeCryptoStagingOrderBookBookMessage, cls).__new__(cls, message_type, content, timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return self.content["update_id"]
        else:
            return -1

    @property
    def first_update_id(self) -> int:
        if self.type is OrderBookMessageType.DIFF:
            return self.content.get("first_update_id", self.update_id)
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return self.content["trade_id"]
        return -1

    @property
    def trading_pair(self) -> str:
        return self.content["trading_pair"]

    @property
    def asks(self) -> List[OrderBookRow]:
        if self.content["asks"]:
            if "price" in self.content["asks"][0]:
                results = [
                    OrderBookRow(float(entry["price"]) , float(entry["remaining_volume"]), self.update_id)
                    for entry in self.content["asks"]
                ]
                sorted(results, key=lambda a: a.price)
            else:
                results = [
                    OrderBookRow(float(str(entry[0])), 0 if entry[1] == '' else float(str(entry[1])), self.update_id)
                    for entry in self.content["asks"]
                ]
        else:
            results = []
        return results

    @property
    def bids(self) -> List[OrderBookRow]:
        if self.content["bids"]:
            if "price" in self.content["bids"][0]:
                results = [
                    OrderBookRow(float(entry["price"]) , float(entry["remaining_volume"]), self.update_id)
                    for entry in self.content["bids"]
                ]
                sorted(results, key=lambda a: a.price)
            else:
                results = [
                    OrderBookRow(float(str(entry[0])), 0 if entry[1] == '' else float(str(entry[1])), self.update_id)
                    for entry in self.content["bids"]
                ]
        else:
            results = []
        return results

    @property
    def has_update_id(self) -> bool:
        return self.type in {OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT}

    @property
    def has_trade_id(self) -> bool:
        return self.type == OrderBookMessageType.TRADE

    def __eq__(self, other: "OrderBookMessage") -> bool:
        eq = (
            (self.type == other.type)
            and (
                (self.has_update_id and (self.update_id == other.update_id))
                or (self.trade_id == other.trade_id)
            )
        )
        return eq

    def __hash__(self):
        return hash(self.type, self.update_id, self.trade_id)

    def __lt__(self, other: "OrderBookMessage") -> bool:
        eq = (
            (self.has_update_id and other.has_update_id and self.update_id < other.update_id)
            or (self.has_trade_id and other.has_trade_id and self.trade_id < other.trade_id)
            or (
                ((self.timestamp != other.timestamp) and self.timestamp < other.timestamp)
                or self.has_update_id  # if same timestamp, order book messages < trade messages.
            )
        )
        return eq
