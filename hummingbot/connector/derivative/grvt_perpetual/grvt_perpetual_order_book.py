from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class GrvtPerpetualOrderBook(OrderBook):
    @staticmethod
    def _price_levels(levels: Any) -> list:
        return [[level["price"], level["size"]] for level in levels]

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg)
        if metadata:
            data.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": data["trading_pair"],
                "update_id": int(data["event_time"]),
                "bids": cls._price_levels(data["bids"]),
                "asks": cls._price_levels(data["asks"]),
            },
            timestamp=int(data["event_time"]) * 1e-9 if "event_time" in data else timestamp,
        )

    @classmethod
    def snapshot_message_from_ws(
        cls,
        msg: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg["feed"])
        if metadata:
            data.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": data["trading_pair"],
                "update_id": int(data["event_time"]),
                "bids": cls._price_levels(data["bids"]),
                "asks": cls._price_levels(data["asks"]),
            },
            timestamp=int(data["event_time"]) * 1e-9,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg["feed"])
        if metadata:
            data.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": data["trading_pair"],
                "update_id": int(data["event_time"]),
                "bids": cls._price_levels(data["bids"]),
                "asks": cls._price_levels(data["asks"]),
            },
            timestamp=int(data["event_time"]) * 1e-9,
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg["feed"])
        if metadata:
            data.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": data["trading_pair"],
                "trade_type": float(TradeType.BUY.value) if data["is_taker_buyer"] else float(TradeType.SELL.value),
                "trade_id": data["trade_id"],
                "update_id": int(data["event_time"]),
                "price": data["price"],
                "amount": data["size"],
            },
            timestamp=int(data["event_time"]) * 1e-9,
        )
