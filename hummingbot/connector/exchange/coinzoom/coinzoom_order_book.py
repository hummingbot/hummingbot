import logging

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants
from hummingbot.connector.exchange.coinzoom.coinzoom_order_book_message import CoinzoomOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.logger import HummingbotLogger

from .coinzoom_utils import (
    convert_from_exchange_trading_pair,
    str_date_to_ts,
)

_logger = None


class CoinzoomOrderBook(OrderBook):
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
        :return: CoinzoomOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return CoinzoomOrderBookMessage(
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
        :return: CoinzoomOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return CoinzoomOrderBookMessage(
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
        :param record: a trade data from the database
        :return: CoinzoomOrderBookMessage
        """

        trade_msg = {
            "price": msg[1],
            "amount": msg[2],
            "trading_pair": convert_from_exchange_trading_pair(msg[0]),
            "trade_type": None,
        }
        trade_timestamp = str_date_to_ts(msg[3])

        return CoinzoomOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=trade_msg,
            timestamp=trade_timestamp
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError(Constants.EXCHANGE_NAME + " order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError(Constants.EXCHANGE_NAME + " order book needs to retain individual order data.")
