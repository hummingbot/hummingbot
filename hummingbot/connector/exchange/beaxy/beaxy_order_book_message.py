import time
from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BeaxyOrderBookMessage(OrderBookMessage):
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
                raise ValueError('timestamp must not be None when initializing snapshot messages.')
                timestamp = int(time.time())
        return super(BeaxyOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        return int(str(self.content['sequenceNumber']))

    @property
    def trade_id(self) -> int:
        return int(self.timestamp * 1e3)

    def _entries(self, side):
        return [
            OrderBookRow(entry['price'], entry['quantity'], self.update_id)
            if entry['action'] != 'DELETE' else OrderBookRow(entry['price'], 0, self.update_id)
            for entry in self.content.get('entries', [])
            if entry['side'] == side
        ]

    @property
    def asks(self) -> List[OrderBookRow]:
        return self._entries('ASK')

    @property
    def bids(self) -> List[OrderBookRow]:
        return self._entries('BID')

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
