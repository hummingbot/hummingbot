# -*- coding: utf-8 -*-

import logging
from typing import Dict, Optional, Any, List
from decimal import Decimal

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

from hummingbot.connector.exchange.beaxy.beaxy_order_book_message import BeaxyOrderBookMessage
from hummingbot.connector.exchange.beaxy.beaxy_misc import symbol_to_trading_pair


_bxob_logger = None


cdef class BeaxyOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _bxob_logger
        if _bxob_logger is None:
            _bxob_logger = logging.getLogger(__name__)
        return _bxob_logger

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BeaxyOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BeaxyOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        ts = msg['timestamp']
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            'trading_pair': symbol_to_trading_pair(msg['symbol']),
            'trade_type': float(TradeType.SELL.value) if msg['side'] == 'SELL' else float(TradeType.BUY.value),
            'price': Decimal(str(msg['price'])),
            'update_id': ts,
            'amount': msg['size']
        }, timestamp=ts * 1e-3)

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError('Beaxy order book needs to retain individual order data.')

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError('Beaxy order book needs to retain individual order data.')
