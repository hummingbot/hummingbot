#!/usr/bin/env python

import logging
from datetime import datetime
from typing import Dict, Optional

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_utils import convert_from_exchange_trading_pair
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger

_btob_logger = None


class FtxPerpetualOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _btob_logger
        if _btob_logger is None:
            _btob_logger = logging.getLogger(__name__)
        return _btob_logger

    @classmethod
    def restful_snapshot_message_from_exchange(cls,
                                               msg: Dict[str, any],
                                               timestamp: float,
                                               metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,
            "bids": msg["result"]["bids"],
            "asks": msg["result"]["asks"]
        }, timestamp=timestamp)

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": convert_from_exchange_trading_pair(msg["market"]),
            "update_id": int(timestamp),
            "bids": msg["data"]["bids"],
            "asks": msg["data"]["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": convert_from_exchange_trading_pair(msg["market"]),
            "update_id": timestamp,
            "bids": msg["data"]["bids"],
            "asks": msg["data"]["asks"]
        }, timestamp=timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        ts = datetime.timestamp(datetime.strptime(msg["time"], "%Y-%m-%dT%H:%M:%S.%f+00:00"))
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": convert_from_exchange_trading_pair(msg["market"]),
            "trade_type": float(TradeType.SELL.value) if msg["side"] == "sell" else float(TradeType.BUY.value),
            "trade_id": msg["id"],
            "update_id": ts,
            "price": msg["price"],
            "amount": msg["size"]
        }, timestamp=ts)
