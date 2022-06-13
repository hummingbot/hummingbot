from typing import Dict, Union

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class BlockchainComOrderBookMessage(OrderBookMessage):

    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Union[float, None] = None,
        *args,
        **kwargs,
    ):
        return super(OrderBookMessage, cls).__new__(cls, message_type, content, timestamp, *args, **kwargs)

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            return self.content['update_id']
        else:
            return -1

    @property
    def bids(self):
        return [OrderBookRow(float(bid['px']), bid['num'], self.update_id) for bid in self.content['bids']]

    @property
    def asks(self):
        return [OrderBookRow(float(bid['px']), bid['num'], self.update_id) for bid in self.content['asks']]
