from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

class BlockchainComOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict]):
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT
        )