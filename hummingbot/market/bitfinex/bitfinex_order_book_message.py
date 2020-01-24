from typing import (
    Dict,
    Optional,
)

import pandas as pd

from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.market.bitfinex import ContentEventType


class BitfinexOrderBookMessage(OrderBookMessage):
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
                raise ValueError(
                    "timestamp must not be None when initializing snapshot messages.")

            timestamp = pd.Timestamp(content["time"], tz="UTC").timestamp()

        return super(BitfinexOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        return int(self.timestamp)

    @property
    def trade_id(self) -> int:
        return self.content["trade_id"]

    @property
    def trading_pair(self) -> str:
        return self.content["symbol"]

    @property
    def event_info(self):
        if isinstance(self.content, dict):
            return self.content["event"] == ContentEventType.INFO

    @property
    def event_auth(self):
        if isinstance(self.content, dict):
            return self.content["event"] == ContentEventType.AUTH

    @property
    def type_heartbeat(self):
        return self.content[1] == ContentEventType.HEART_BEAT if isinstance(self.content, list) else None
