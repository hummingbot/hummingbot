
import time
from typing import Dict, Optional, Union

from hummingbot.connector.exchange.blockchain_com.blockchain_com_order_book_message import BlockchainComOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

# TODO: Send this in the API response
update_id = 1


class BlockchainComOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], timestamp: Union[float, None], metadata: Optional[Dict]) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BlockchainComOrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["symbol"],
                "update_id": time.time(),
                "bids": msg["bids"],
                "asks": msg["asks"]
            },
            timestamp=timestamp
        )
