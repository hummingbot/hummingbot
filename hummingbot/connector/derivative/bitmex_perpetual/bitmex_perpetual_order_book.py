import logging
from datetime import datetime
from typing import Dict, Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger


class BitmexPerpetualOrderBook(OrderBook):
    _bpob_logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._baobds_logger is None:
            cls._baobds_logger = logging.getLogger(__name__)
        return cls._baobds_logger

    @classmethod
    def snapshot_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        data = msg["data_dict"]
        if metadata:
            data.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data["symbol"],
            "update_id": timestamp,
            "bids": data["bids"],
            "asks": data["asks"]
        }, timestamp=timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        data = msg
        if metadata:
            data.update(metadata)
        timestamp = datetime.timestamp(datetime.strptime(data["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"))
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": data["symbol"],
            "trade_type": float(TradeType.SELL.value) if data["side"] == "Sell" else float(TradeType.BUY.value),
            "trade_id": timestamp,
            "update_id": timestamp,
            "price": data["price"],
            "amount": data["size"]
        }, timestamp=timestamp)
