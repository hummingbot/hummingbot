
import logging
from typing import (
    Any,
    Optional,
    Dict
)

from hummingbot.connector.exchange.mexc.mexc_order_book_message import MexcOrderBookMessage
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

_logger = None


class MexcOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__),
        return _logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       trading_pair: str,
                                       timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(timestamp * 1e-3)
        content = {
            "trading_pair": trading_pair,
            "update_id": msg_ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }
        return MexcOrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp or msg_ts)

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(timestamp * 1e-3)
        content = {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["T"] == 2 else float(TradeType.BUY.value),
            "trade_id": msg["t"],
            "update_id": msg["t"],
            "amount": msg["q"],
            "price": msg["p"]
        }
        return MexcOrderBookMessage(OrderBookMessageType.TRADE, content, timestamp or msg_ts)

    @classmethod
    def diff_message_from_exchange(cls,
                                   data: Dict[str, Any],
                                   timestamp: float = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            data.update(metadata)

        msg_ts = int(timestamp * 1e-3)
        content = {
            "trading_pair": data["trading_pair"],
            "update_id": msg_ts,
            "bids": data.get("bids", []),
            "asks": data.get("asks", [])
        }
        return MexcOrderBookMessage(OrderBookMessageType.DIFF, content, timestamp or msg_ts)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> OrderBook:
        retval = MexcOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
