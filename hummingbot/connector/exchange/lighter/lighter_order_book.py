from typing import Any, Dict, List

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class LighterOrderBook(OrderBook):
    @staticmethod
    def _ws_levels(levels: List[Dict[str, Any]]) -> List[List[float]]:
        return [[float(level["price"]), float(level["size"])] for level in levels]

    @staticmethod
    def _rest_levels(levels: List[Dict[str, Any]]) -> List[List[float]]:
        return [
            [float(level["price"]), float(level["remaining_base_amount"])]
            for level in levels
        ]

    @classmethod
    def snapshot_message_from_rest(
        cls,
        msg: Dict[str, Any],
        trading_pair: str,
    ) -> OrderBookMessage:
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": 0,
                "bids": cls._rest_levels(msg.get("bids", [])),
                "asks": cls._rest_levels(msg.get("asks", [])),
            },
            timestamp=0,
        )

    @classmethod
    def snapshot_message_from_ws(
        cls,
        msg: Dict[str, Any],
        trading_pair: str,
    ) -> OrderBookMessage:
        order_book = msg["order_book"]
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": int(order_book["nonce"]),
                "bids": cls._ws_levels(order_book.get("bids", [])),
                "asks": cls._ws_levels(order_book.get("asks", [])),
            },
            timestamp=float(msg["timestamp"]) * 1e-3,
        )

    @classmethod
    def diff_message_from_ws(
        cls,
        msg: Dict[str, Any],
        trading_pair: str,
    ) -> OrderBookMessage:
        order_book = msg["order_book"]
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": trading_pair,
                "update_id": int(order_book["nonce"]),
                "first_update_id": int(order_book.get("begin_nonce", order_book["nonce"])),
                "bids": cls._ws_levels(order_book.get("bids", [])),
                "asks": cls._ws_levels(order_book.get("asks", [])),
            },
            timestamp=float(msg["timestamp"]) * 1e-3,
        )

    @classmethod
    def trade_message_from_ws(
        cls,
        trade: Dict[str, Any],
        trading_pair: str,
    ) -> OrderBookMessage:
        trade_type = TradeType.BUY if trade.get("is_maker_ask", False) else TradeType.SELL
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": trading_pair,
                "trade_type": float(trade_type.value),
                "trade_id": str(trade["trade_id"]),
                "price": float(trade["price"]),
                "amount": float(trade["size"]),
            },
            timestamp=float(trade.get("transaction_time", 0)) * 1e-6,
        )
