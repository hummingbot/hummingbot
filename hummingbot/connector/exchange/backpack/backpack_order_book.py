from typing import Any, Dict, List, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BackpackOrderBook(OrderBook):
    """
    Order book implementation for Backpack Exchange.

    Handles parsing of order book snapshots and updates from both REST and WebSocket.
    """

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: float,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        Create a snapshot message from exchange REST response.

        Backpack depth response format:
        {
            "lastUpdateId": "1234567890",
            "bids": [["50000.00", "1.5"], ...],  # [price, quantity]
            "asks": [["50001.00", "2.0"], ...]
        }

        Args:
            msg: The response from /api/v1/depth
            timestamp: The snapshot timestamp
            metadata: Extra information (e.g., trading_pair)

        Returns:
            OrderBookMessage with snapshot data
        """
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg.get("trading_pair", ""),
                "update_id": int(msg.get("lastUpdateId", timestamp * 1000)),
                "bids": cls._parse_orders(msg.get("bids", [])),
                "asks": cls._parse_orders(msg.get("asks", [])),
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        Create a diff message from WebSocket depth update.

        Backpack WebSocket depth format:
        {
            "stream": "depth.BTC_USDC",
            "data": {
                "e": "depthUpdate",
                "s": "BTC_USDC",
                "b": [["50000.00", "1.5"], ...],  # bids
                "a": [["50001.00", "2.0"], ...],  # asks
                "u": 1234567890,  # update ID
                "T": 1699999999999  # timestamp in microseconds
            }
        }

        Args:
            msg: The WebSocket depth update
            timestamp: The update timestamp
            metadata: Extra information

        Returns:
            OrderBookMessage with diff data
        """
        if metadata:
            msg.update(metadata)

        data = msg.get("data", msg)

        update_ts = timestamp
        if "T" in data:
            update_ts = float(data["T"]) / 1e6  # Convert microseconds to seconds

        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": msg.get("trading_pair", ""),
                "update_id": int(data.get("u", update_ts * 1000)),
                "bids": cls._parse_orders(data.get("b", data.get("bids", []))),
                "asks": cls._parse_orders(data.get("a", data.get("asks", []))),
            },
            timestamp=update_ts,
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        Create a trade message from WebSocket trade event.

        Backpack WebSocket trade format:
        {
            "stream": "trade.BTC_USDC",
            "data": {
                "e": "trade",
                "s": "BTC_USDC",
                "p": "50000.00",    # price
                "q": "0.5",         # quantity
                "m": true,          # is buyer maker
                "t": 1234567890,    # trade ID
                "T": 1699999999999  # timestamp in microseconds
            }
        }

        Args:
            msg: The WebSocket trade event
            metadata: Extra information

        Returns:
            OrderBookMessage with trade data
        """
        if metadata:
            msg.update(metadata)

        data = msg.get("data", msg)

        # Determine trade type based on buyer/maker flag
        # If buyer is maker, then the trade was initiated by a seller (SELL)
        is_buyer_maker = data.get("m", False)
        trade_type = TradeType.SELL if is_buyer_maker else TradeType.BUY

        timestamp = float(data.get("T", 0)) / 1e6  # Convert microseconds to seconds

        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg.get("trading_pair", ""),
                "trade_type": float(trade_type.value),
                "trade_id": str(data.get("t", data.get("id", timestamp))),
                "price": float(data.get("p", data.get("price", 0))),
                "amount": float(data.get("q", data.get("quantity", 0))),
            },
            timestamp=timestamp,
        )

    @classmethod
    def _parse_orders(cls, orders: List) -> List[List[float]]:
        """
        Parse order book entries from Backpack format.

        Args:
            orders: List of [price, quantity] pairs as strings or floats

        Returns:
            List of [price, quantity] pairs as floats
        """
        result = []
        for order in orders:
            if isinstance(order, (list, tuple)) and len(order) >= 2:
                price = float(order[0])
                quantity = float(order[1])
                result.append([price, quantity])
            elif isinstance(order, dict):
                price = float(order.get("price", order.get("px", 0)))
                quantity = float(order.get("quantity", order.get("sz", 0)))
                result.append([price, quantity])
        return result
