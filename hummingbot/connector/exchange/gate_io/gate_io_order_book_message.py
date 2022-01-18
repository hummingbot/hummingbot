#!/usr/bin/env python

from typing import Dict, List, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow

from .gate_io_utils import convert_from_exchange_trading_pair


class GateIoOrderBookMessage(OrderBookMessage):
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

        return super(GateIoOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.timestamp * 1e3)
        return -1

    @property
    def trading_pair(self) -> str:
        if "trading_pair" in self.content:
            return self.content["trading_pair"]
        elif "currency_pair" in self.content:
            return convert_from_exchange_trading_pair(self.content["currency_pair"])

    # The `asks` and `bids` properties are only used in the methods below.
    # They are all replaced or unused in this connector:
    #     OrderBook.restore_from_snapshot_and_diffs
    #     OrderBookTracker._track_single_book
    #     MockAPIOrderBookDataSource.get_tracking_pairs
    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book uses active_order_tracker.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book uses active_order_tracker.")

    def __eq__(self, other) -> bool:
        return (type(self) == type(other)
                and self.type == other.type
                and self.update_id == other.update_id
                and self.timestamp == other.timestamp)

    def __hash__(self):
        return hash((self.type, self.update_id, self.timestamp))

    def __lt__(self, other) -> bool:
        return (self.update_id < other.update_id or
                (self.update_id == other.update_id and self.timestamp < other.timestamp) or
                (self.update_id == other.update_id and
                 self.timestamp == other.timestamp
                 and self.type.value < other.type.value))
