#!/usr/bin/env python

import logging

# from sqlalchemy.engine import RowProxy
from typing import Any, Dict, List, Optional

import hummingbot.connector.exchange.xago_io.xago_io_constants as constants
from hummingbot.connector.exchange.xago_io.xago_io_order_book_message import XagoIoOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult
from hummingbot.logger import HummingbotLogger

_logger = None


class XagoIoOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__)
        return _logger


    @classmethod
    def snapshot_message_from_exchange_rest(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None):
        """
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: XagoIoOrderBookMessage
        """

        if metadata:
            msg.update(metadata)


        return XagoIoOrderBookMessage(OrderBookMessageType.SNAPSHOT,{
            "trading_pair": metadata["trading_pair"],
            "update_id": 0,
            "bids": msg["buyOrders"] if 'buyOrders' in msg else [],
            "asks": msg["sellOrders"] if 'sellOrders' in msg else [],
            "is_websocket_payload": False
        }, timestamp=timestamp)

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None):
        """
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: XagoIoOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        return XagoIoOrderBookMessage(OrderBookMessageType.SNAPSHOT,{
            "trading_pair": metadata["trading_pair"],
            "update_id": metadata["sequence"],
            "bids": msg["bids"] if 'bids' in msg else [],
            "asks": msg["asks"] if 'asks' in msg else [],
            "is_websocket_payload": True
        }, timestamp=timestamp)

    # @classmethod
    # def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
    #     """
    #     *used for backtesting
    #     Convert a row of snapshot data into standard OrderBookMessage format
    #     :param record: a row of snapshot data from the database
    #     :return: XagoIoOrderBookMessage
    #     """
    #     return XagoIoOrderBookMessage(
    #         message_type=OrderBookMessageType.SNAPSHOT,
    #         content=record.json,
    #         timestamp=record.timestamp
    #     )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        """
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: XagoIoOrderBookMessage
        """

        if metadata:
            msg.update(metadata)


        return XagoIoOrderBookMessage(OrderBookMessageType.DIFF,{
            "trading_pair": metadata["trading_pair"],
            "update_id": msg["sequence"],
            "bids": [msg["bids"]] if 'bids' in msg else [],
            "asks": [msg["asks"]] if 'asks' in msg else [],
            "is_websocket_payload": True,
        }, timestamp=timestamp)

    # @classmethod
    # def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
    #     """
    #     *used for backtesting
    #     Convert a row of diff data into standard OrderBookMessage format
    #     :param record: a row of diff data from the database
    #     :return: XagoIoOrderBookMessage
    #     """
    #     return XagoIoOrderBookMessage(
    #         message_type=OrderBookMessageType.DIFF,
    #         content=record.json,
    #         timestamp=record.timestamp
    #     )


    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :param record: a trade data from the database
        :return: XagoIoOrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        msg.update({
            "exchange_order_id": msg.get("d"),
            "trade_type": msg.get("s"),
            "price": msg.get("p"),
            "amount": msg.get("q"),
        })

        return XagoIoOrderBookMessage(
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
