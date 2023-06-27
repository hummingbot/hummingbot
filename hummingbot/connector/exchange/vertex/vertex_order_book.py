from typing import Any, Dict, Optional

from hummingbot.connector.exchange.vertex.vertex_utils import convert_from_x18, convert_timestamp
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class VertexOrderBook(OrderBook):
    @classmethod
    def snapshot_message_from_exchange_websocket(
        cls, msg: Dict[str, Any], timestamp: float, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = msg["data"]["timestamp"]
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int(ts),
                "bids": convert_from_x18(msg["data"]["bids"]),
                "asks": convert_from_x18(msg["data"]["asks"]),
            },
            timestamp=timestamp,
        )

    @classmethod
    def snapshot_message_from_exchange_rest(
        cls, msg: Dict[str, Any], timestamp: float, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = msg["data"]["timestamp"]
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int(ts),
                "bids": convert_from_x18(msg["data"]["bids"]),
                "asks": convert_from_x18(msg["data"]["asks"]),
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls, msg: Dict[str, Any], timestamp: Optional[float] = None, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = convert_timestamp(msg["last_max_timestamp"])
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int(msg["last_max_timestamp"]),
                "bids": convert_from_x18(msg["bids"]),
                "asks": convert_from_x18(msg["asks"]),
            },
            timestamp=ts,
        )

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, Any], metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = convert_timestamp(msg["timestamp"])
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.BUY.value) if msg["is_taker_buyer"] else float(TradeType.SELL.value),
                "trade_id": int(msg["timestamp"]),
                "update_id": int(msg["timestamp"]),
                "price": convert_from_x18(msg["price"]),
                "amount": convert_from_x18(msg["taker_qty"]),
            },
            timestamp=ts,
        )
