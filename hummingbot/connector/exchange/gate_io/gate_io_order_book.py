import logging

from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.common import TradeType
from hummingbot.logger import HummingbotLogger

_logger = None


class GateIoOrderBook(OrderBook):
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
        :return: GateIoOrderBookMessage
        """
        extra_data = metadata or {}
        extra_data["update_id"] = msg["id"]
        msg.update(extra_data)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg["update_id"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        """
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: GateIoOrderBookMessage
        """

        extra_data = metadata or {}
        extra_data["update_id"] = msg["u"]
        msg.update(extra_data)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "first_update_id": msg["U"],
            "update_id": msg["u"],
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=timestamp)
        # TODO should we use timestamp coming from the message?

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :param record: a trade data from the database
        :return: GateIoOrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        msg.update({
            "trade_id": msg.get("id"),
            "trade_type": msg.get("side"),
            "price": msg.get("price"),
            "amount": msg.get("amount"),
        })
        # TODO should we use timestamp coming from the message?
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["side"] == "sell" else float(TradeType.BUY.value),
            "trade_id": msg["trade_id"],
            # "update_id": ts,
            "update_id": timestamp,
            "price": msg["price"],
            "amount": msg["amount"]
        }, timestamp=timestamp)
        # }, timestamp=ts * 1e-3)

    # TODO
    @classmethod
    def __from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book needs to retain individual order data.")

    @classmethod
    def __restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book needs to retain individual order data.")
