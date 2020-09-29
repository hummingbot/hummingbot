#!/usr/bin/env python

import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import TradeType
from hummingbot.connector.exchange.bittrex.bittrex_order_book_message import BittrexOrderBookMessage
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)

_btob_logger = None

cdef class BittrexOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _btob_logger
        if _btob_logger is None:
            _btob_logger = logging.getLogger(__name__)
        return _btob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BittrexOrderBookMessage(
            OrderBookMessageType.SNAPSHOT, {
                "trading_pair": msg["marketSymbol"],
                "update_id": int(msg["sequence"]),
                "bids": msg["bid"],
                "asks": msg["ask"]
            }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        return BittrexOrderBookMessage(
            OrderBookMessageType.DIFF, {
                "trading_pair": msg["marketSymbol"],
                "update_id": int(msg["sequence"]),
                "bids": msg["bidDeltas"],
                "asks": msg["askDeltas"]
            }, timestamp=timestamp)

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BittrexOrderBookMessage(
            OrderBookMessageType.TRADE, {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.BUY.value) if msg["takerSide"] == "BUY"
                else float(TradeType.SELL.value),
                "trade_id": msg["id"],
                "update_id": msg["sequence"],
                "price": msg["rate"],
                "amount": msg["quantity"]
            }, timestamp=timestamp)

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("Bittrex order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("Bittrex order book needs to retain individual order data.")
