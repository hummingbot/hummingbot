import logging
from typing import Optional, Dict
from decimal import Decimal

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book_message import DydxPerpetualOrderBookMessage


class DydxPerpetualOrderBook(OrderBook):
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
        if msg["rest"]:
            bids = [{"price": Decimal(bid["price"]), "amount": Decimal(bid["size"])} for bid in msg["bids"]]
            asks = [{"price": Decimal(ask["price"]), "amount": Decimal(ask["size"])} for ask in msg["asks"]]
        else:
            bids = [{"price": Decimal(bid['price']), "amount": Decimal(bid['size'])} for bid in msg["bids"]]
            asks = [{"price": Decimal(ask['price']), "amount": Decimal(ask['size'])} for ask in msg["asks"]]
        return DydxPerpetualOrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls, msg: Dict[str, any], timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        bids = [{"price": Decimal(bid[0]), "amount": Decimal(bid[1])} for bid in msg["bids"]]
        asks = [{"price": Decimal(ask[0]), "amount": Decimal(ask[1])} for ask in msg["asks"]]
        return DydxPerpetualOrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
        }, timestamp=timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        return DydxPerpetualOrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["id"],
            "trade_type": msg["side"],
            "trade_id": msg["ts"],
            "update_id": msg["ts"],
            "price": Decimal(msg["price"]),
            "amount": Decimal(msg["size"])
        }, timestamp=msg["ts"] * 1e-3)
