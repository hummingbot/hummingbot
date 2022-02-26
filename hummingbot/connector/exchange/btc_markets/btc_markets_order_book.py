#!/usr/bin/env python

import logging
import hummingbot.connector.exchange.btc_markets.btc_markets_constants as constants

from typing import (
    Optional,
    Dict,
    List, Any)
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage, OrderBookMessageType
)
from hummingbot.connector.exchange.btc_markets.btc_markets_order_book_message import BtcMarketsOrderBookMessage

_logger = None


class BtcMarketsOrderBook(OrderBook):
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
        :return: BtcMarketsOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return BtcMarketsOrderBookMessage(
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
        :return: BtcMarketsOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return BtcMarketsOrderBookMessage(
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
        :return: BtcMarketsOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        msg.update({
            "exchange_order_id": msg.get("tradeId"),
            "trade_type": msg.get("side"),
            "amount": msg.get("volume"),
        })
        """
        if msg['trade_type'] == 'Bid':
            msg['trade_type'] = 'BUY'
        elif msg['trade_type'] == 'Ask':
            msg['trade_type'] = 'SELL'
        """
        return BtcMarketsOrderBookMessage(
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
