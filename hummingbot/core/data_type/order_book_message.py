#!/usr/bin/env python

from collections import namedtuple
from enum import Enum
from functools import total_ordering
import pandas as pd
from typing import (
    Optional,
    List,
    Dict
)

from hummingbot.core.data_type.order_book_row import OrderBookRow


class OrderBookMessageType(Enum):
    SNAPSHOT = 1
    DIFF = 2
    TRADE = 3


@total_ordering
class OrderBookMessage(namedtuple("_OrderBookMessage", "type, content, timestamp")):
    type: OrderBookMessageType
    content: Dict[str, any]
    timestamp: float

    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        return super(OrderBookMessage, cls).__new__(cls, message_type, content, timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return self.content["update_id"]
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return self.content["trade_id"]
        return -1

    @property
    def symbol(self) -> str:
        return self.content["symbol"]

    @property
    def asks(self) -> List[OrderBookRow]:
        return [OrderBookRow(float(price), float(amount), self.update_id)
                for price, amount, *trash in self.content["asks"]]

    @property
    def bids(self) -> List[OrderBookRow]:
        return [OrderBookRow(float(price), float(amount), self.update_id)
                for price, amount, *trash in self.content["bids"]]

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

    def __lt__(self, other: "OrderBookMessage") -> bool:
        if self.has_update_id and other.has_update_id:
            return self.update_id < other.update_id
        elif self.has_trade_id and other.has_trade_id:
            return self.trade_id < other.trade_id
        else:
            if self.timestamp != other.timestamp:
                return self.timestamp < other.timestamp
            else:
                # For messages of same timestamp, order book messages come before trade messages.
                return self.has_update_id


class DDEXOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = content["time"] * 1e-3
        return super(DDEXOrderBookMessage, cls).__new__(cls, message_type, content,
                                                        timestamp=timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def symbol(self) -> str:
        return self.content["marketId"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("DDEX order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("DDEX order book messages have different semantics.")

    @property
    def has_update_id(self) -> bool:
        return True

    @property
    def has_trade_id(self) -> bool:
        return True

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


class IDEXOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                timestamp = 0.0
            else:
                datetime_str: str = content.get("updatedAt") or content.get("createdAt")
                if datetime_str is None:
                    raise ValueError(f"Invalid time for this diff message: {content}")
                timestamp = pd.Timestamp(datetime_str, tz="UTC").timestamp()
        return super(IDEXOrderBookMessage, cls).__new__(cls, message_type, content,
                                                        timestamp=timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def symbol(self) -> str:
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


class RadarRelayOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if message_type is OrderBookMessageType.SNAPSHOT and timestamp is None:
            raise ValueError("timestamp must not be None when initializing snapshot messages.")

        elif message_type is OrderBookMessageType.DIFF and content["action"] in ["NEW"]:
            timestamp = pd.Timestamp(content["event"]["order"]["createdDate"], tz="UTC").timestamp()
        elif message_type is OrderBookMessageType.DIFF and content["action"] in ["FILL"]:
            timestamp = content["event"]["timestamp"]
        elif message_type is OrderBookMessageType.TRADE:
            timestamp = content["event"]["timestamp"]
        elif timestamp is None:
            raise ValueError("timestamp field required for this message.")

        return super(RadarRelayOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def symbol(self) -> str:
        return self.content["symbol"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("RadarRelay order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("RadarRelay order book messages have different semantics.")

    @property
    def has_update_id(self) -> bool:
        return True

    @property
    def has_trade_id(self) -> bool:
        return True

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


class BambooRelayOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if message_type is OrderBookMessageType.SNAPSHOT and timestamp is None:
            raise ValueError("timestamp must not be None when initializing snapshot messages.")

        elif message_type is OrderBookMessageType.DIFF and content["action"] in ["NEW"]:
            timestamp = pd.Timestamp(content["event"]["order"]["createdDate"], tz="UTC").timestamp()
        elif message_type is OrderBookMessageType.DIFF and content["action"] in ["FILL"]:
            timestamp = content["event"]["timestamp"]
        elif message_type is OrderBookMessageType.TRADE:
            timestamp = content["event"]["timestamp"]
        elif timestamp is None:
            raise ValueError("timestamp field required for this message.")

        return super(BambooRelayOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def symbol(self) -> str:
        return self.content["symbol"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("BambooRelay order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("BambooRelay order book messages have different semantics.")

    @property
    def has_update_id(self) -> bool:
        return True

    @property
    def has_trade_id(self) -> bool:
        return True

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


class CoinbaseProOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = pd.Timestamp(content["time"], tz="UTC").timestamp()
        return super(CoinbaseProOrderBookMessage, cls).__new__(cls, message_type, content,
                                                               timestamp=timestamp, *args, **kwargs)

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
    def symbol(self) -> str:
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


class BittrexOrderBookMessage(OrderBookMessage):
    def __new__(cls, message_type: OrderBookMessageType, content: Dict[str, any], timestamp: Optional[float] = None,
                *args, **kwargs):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = pd.Timestamp(content["time"], tz="UTC").timestamp()
        return super(BittrexOrderBookMessage, cls).__new__(cls, message_type, content,
                                                           timestamp=timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    @property
    def symbol(self) -> str:
        return self.content["market"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("Bittrex order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("Bittrex order book messages have different semantics.")

    @property
    def has_update_id(self) -> bool:
        return True

    @property
    def has_trade_id(self) -> bool:
        return True

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
