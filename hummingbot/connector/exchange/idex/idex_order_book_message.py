import pandas as pd
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


class IdexOrderBookMessage(OrderBookMessage):
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
            timestamp = pd.Timestamp(content["data"]["t"], unit="ms").timestamp()
        return super(IdexOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type is OrderBookMessageType.SNAPSHOT:
            # sequence numbers can be found in self.content["sequence"] for SNAPSHOT orderbook messages
            return int(self.content["sequence"])
        elif self.type is OrderBookMessageType.DIFF:
            # sequence numbers can be found in self.content["data"]["u"] for DIFF orderbook messages
            return int(self.content["data"]["u"])
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.content["data"]["u"])
        return -1

    @property
    def trading_pair(self) -> str:
        # Trading pairs in DIFF/TRADE orderbook messages found in self.content["data"]["m"].
        # Trading pairs in SNAPSHOT orderbook messages found in self.content["trading_pair"]
        if self.content.get("data"):
            return self.content["data"]["m"]
        else:
            return self.content["trading_pair"]

    @property
    def asks(self) -> List[OrderBookRow]:
        raise NotImplementedError("Idex order book messages have different semantics.")

    @property
    def bids(self) -> List[OrderBookRow]:
        raise NotImplementedError("Idex order book messages have different semantics.")
