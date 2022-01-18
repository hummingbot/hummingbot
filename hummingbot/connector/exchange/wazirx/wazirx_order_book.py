import logging

from typing import (
    Optional,
    Dict,
    List, Any)
import hummingbot.connector.exchange.wazirx.wazirx_constants as constants
from hummingbot.connector.exchange.wazirx.wazirx_order_book_message import WazirxOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.logger import HummingbotLogger

_logger = None


class WazirxOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__)
        return _logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None):
        """
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: WazirxOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return WazirxOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        """
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: WazirxOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return WazirxOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :param record: a trade data from the exchange
        :return: WazirxOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        msg.update({
            "trade_type": float(TradeType.SELL.value) if msg["S"] == "sell" else float(TradeType.BUY.value),
            "trade_id": msg.get("t"),
            "update_id": timestamp,
            "price": msg.get("p"),
            "amount": msg.get("q"),
        })

        return WazirxOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError(constants.EXCHANGE_NAME + " order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError(constants.EXCHANGE_NAME + " order book needs to retain individual order data.")
