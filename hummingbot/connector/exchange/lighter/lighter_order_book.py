from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class LighterOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int(msg["update_id"]),
                "bids": msg.get("bids", []),
                "asks": msg.get("asks", []),
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": msg["trading_pair"],
                "first_update_id": int(msg["first_update_id"]),
                "update_id": int(msg["update_id"]),
                "bids": msg.get("bids", []),
                "asks": msg.get("asks", []),
            },
            timestamp=timestamp,
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)

        is_maker_ask = bool(msg.get("is_maker_ask"))
        trade_type = float(TradeType.BUY.value) if is_maker_ask else float(TradeType.SELL.value)

        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": trade_type,
                "trade_id": msg.get("trade_id") or msg.get("trade_id_str"),
                "update_id": msg.get("nonce") or msg.get("trade_id") or msg.get("trade_id_str") or 0,
                "price": msg.get("price", "0"),
                "amount": msg.get("size", "0"),
            },
            timestamp=timestamp,
        )
