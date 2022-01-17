import logging
from typing import Optional, Dict

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger


class BinancePerpetualOrderBook(OrderBook):
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
            "update_id": msg["lastUpdateId"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        data = msg["data"]
        if metadata:
            data.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": data["s"],
            "update_id": data["u"],
            "bids": data["b"],
            "asks": data["a"]
        }, timestamp=timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        data = msg["data"]
        if metadata:
            data.update(metadata)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": data["s"],
            "trade_type": float(TradeType.SELL.value) if data["m"] else float(TradeType.BUY.value),
            "trade_id": data["a"],
            "update_id": data["E"],
            "price": data["p"],
            "amount": data["q"]
        }, timestamp=data["E"] * 1e-3)
