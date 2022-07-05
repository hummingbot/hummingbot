import time
from typing import Dict, Optional, Union

from hummingbot.connector.exchange.blockchain_com.blockchain_com_order_book_message import BlockchainComOrderBookMessage
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType

# TODO: Send this in the API response
update_id = 1


class BlockchainComOrderBook(OrderBook):
    @classmethod
    def snapshot_message_from_exchange(
        cls, msg: Dict[str, any], metadata: Union[Dict, None], timestamp: Union[float, None] = None
    ) -> BlockchainComOrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BlockchainComOrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {"trading_pair": msg["symbol"], "update_id": time.time(), "bids": msg["bids"], "asks": msg["asks"]},
            timestamp=timestamp or time.time(),
        )

    @classmethod
    def diff_message_from_exchange(
        cls, msg: Dict[str, any], timestamp: Optional[float] = None, metadata: Optional[Dict] = None
    ):
        raise NotImplementedError()

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        return BlockchainComOrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["symbol"],
                "trade_type": float(TradeType.BUY.value) if msg["side"] == "BUY" else float(TradeType.SELL.value),
                "trade_id": msg["exOrdId"],
                "update_id": msg["timestamp"],
                "price": msg["price"],
                "amount": msg["leavesQty"] + msg["cumQty"],
            },
            timestamp=msg["timestamp"],
        )
