#!/usr/bin/env python

import logging
from typing import Any, Dict, Optional

from hummingbot.connector.exchange.litebit import litebit_utils
from hummingbot.connector.exchange.litebit.litebit_order_book_message import LitebitOrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger

_logger = None


class LitebitOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__)
        return _logger

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from API
        :param metadata: meta data related to msg
        :return: LitebitOrderBookMessage
        """
        if metadata:
            msg.update(metadata)

        return LitebitOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=msg["timestamp"] * 1e-3
        )

    @classmethod
    def diff_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param metadata: meta data related to msg
        :return: LitebitOrderBookMessage
        """
        if metadata:
            msg.update(metadata)

        return LitebitOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=msg["timestamp"] * 1e-3
        )

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, Any], metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :return: LitebitOrderBookMessage
        """
        if metadata:
            msg.update(metadata)

        return LitebitOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": litebit_utils.convert_from_exchange_trading_pair(msg["market"]),
                "trade_type": float(TradeType.SELL.value) if msg["side"] == "sell" else float(TradeType.BUY.value),
                "trade_id": msg["uuid"],
                "update_id": msg["timestamp"],
                "price": msg["price"],
                "amount": msg["amount"]
            },
            timestamp=int(msg["timestamp"] * 1e3)
        )
