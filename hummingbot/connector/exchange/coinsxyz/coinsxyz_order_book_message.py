"""
Order Book Message Format Conversion Utilities for Coins.xyz Exchange.

This module provides utilities to convert between different order book message formats,
specifically handling Coins.xyz API responses and Hummingbot internal formats.
"""

import time
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union

from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class CoinsxyzOrderBookMessage:
    """
    Utility class for converting Coins.xyz order book messages to Hummingbot format.

    Handles conversion between:
    - Coins.xyz REST API responses
    - Coins.xyz WebSocket messages
    - Hummingbot OrderBookMessage format
    """

    @staticmethod
    def snapshot_message_from_exchange(
        msg: Dict[str, Any],
        trading_pair: str,
        timestamp: Optional[float] = None
    ) -> OrderBookMessage:
        """
        Convert Coins.xyz order book snapshot to Hummingbot OrderBookMessage.

        Coins.xyz snapshot format:
        {
            "lastUpdateId": 110426127486,
            "bids": [["109879.000000000000000000", "0.037611600000000000"], ...],
            "asks": [["110437.360000000000000000", "0.000271700000000000"], ...]
        }

        Args:
            msg: Raw message from Coins.xyz API
            trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDT")
            timestamp: Message timestamp (defaults to current time)

        Returns:
            OrderBookMessage with snapshot data
        """
        if timestamp is None:
            timestamp = time.time() * 1000  # Convert to milliseconds

        # Extract data from Coins.xyz response
        update_id = int(msg.get("lastUpdateId", 0))
        raw_bids = msg.get("bids", [])
        raw_asks = msg.get("asks", [])

        # Convert to Decimal format with validation
        bids = CoinsxyzOrderBookMessage._convert_order_book_entries(raw_bids, "bids")
        asks = CoinsxyzOrderBookMessage._convert_order_book_entries(raw_asks, "asks")

        # Create message content
        content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks
        }

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp)

    @staticmethod
    def diff_message_from_exchange(
        msg: Dict[str, Any],
        trading_pair: str,
        timestamp: Optional[float] = None
    ) -> OrderBookMessage:
        """
        Convert Coins.xyz order book diff to Hummingbot OrderBookMessage.

        Coins.xyz WebSocket diff format:
        {
            "stream": "btcusdt@depth",
            "data": {
                "e": "depthUpdate",
                "E": 1756794120409,
                "s": "BTCUSDT",
                "U": 110426127486,
                "u": 110426127487,
                "b": [["109879.00", "0.037611"]],
                "a": [["110437.36", "0.000271"]]
            }
        }

        Args:
            msg: Raw WebSocket message from Coins.xyz
            trading_pair: Trading pair in Hummingbot format
            timestamp: Message timestamp (defaults to current time)

        Returns:
            OrderBookMessage with diff data
        """
        if timestamp is None:
            timestamp = time.time() * 1000

        # Extract data from WebSocket message
        data = msg.get("data", msg)  # Handle both direct data and wrapped format

        update_id = int(data.get("u", data.get("lastUpdateId", 0)))
        raw_bids = data.get("b", data.get("bids", []))
        raw_asks = data.get("a", data.get("asks", []))

        # Convert to Decimal format
        bids = CoinsxyzOrderBookMessage._convert_order_book_entries(raw_bids, "bids")
        asks = CoinsxyzOrderBookMessage._convert_order_book_entries(raw_asks, "asks")

        # Create message content
        content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks
        }

        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp)

    @staticmethod
    def trade_message_from_exchange(
        msg: Dict[str, Any],
        trading_pair: str,
        timestamp: Optional[float] = None
    ) -> OrderBookMessage:
        """
        Convert Coins.xyz trade message to Hummingbot OrderBookMessage.

        Coins.xyz WebSocket trade format:
        {
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "E": 1756794120409,
                "s": "BTCUSDT",
                "t": 12345,
                "p": "109879.00",
                "q": "0.037611",
                "T": 1756794120409,
                "m": true
            }
        }

        Args:
            msg: Raw WebSocket message from Coins.xyz
            trading_pair: Trading pair in Hummingbot format
            timestamp: Message timestamp (defaults to current time)

        Returns:
            OrderBookMessage with trade data
        """
        if timestamp is None:
            timestamp = time.time() * 1000

        # Extract data from WebSocket message
        data = msg.get("data", msg)

        trade_id = str(data.get("t", ""))
        price = Decimal(str(data.get("p", "0")))
        amount = Decimal(str(data.get("q", "0")))
        trade_time = int(data.get("T", timestamp))
        is_buyer_maker = data.get("m", False)

        # Determine trade type (buy/sell from taker perspective)
        trade_type = "sell" if is_buyer_maker else "buy"

        # Create message content
        content = {
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "price": price,
            "amount": amount,
            "trade_id": trade_id,
            "trade_time": trade_time
        }

        return OrderBookMessage(OrderBookMessageType.TRADE, content, timestamp)

    @staticmethod
    def _convert_order_book_entries(
        entries: List[List[Union[str, float]]],
        entry_type: str
    ) -> List[List[Decimal]]:
        """
        Convert order book entries to Decimal format with validation.

        Args:
            entries: List of [price, quantity] entries
            entry_type: "bids" or "asks" for error reporting

        Returns:
            List of [Decimal(price), Decimal(quantity)] entries

        Raises:
            ValueError: If entry format is invalid
        """
        converted_entries = []

        for i, entry in enumerate(entries):
            try:
                if not isinstance(entry, list) or len(entry) != 2:
                    raise ValueError(f"Invalid {entry_type} entry format at index {i}: {entry}")

                price_str, qty_str = entry
                price = Decimal(str(price_str))
                quantity = Decimal(str(qty_str))

                # Validate positive values
                if price <= 0:
                    raise ValueError(f"Invalid {entry_type} price at index {i}: {price}")
                if quantity < 0:  # Allow zero quantity for removal
                    raise ValueError(f"Invalid {entry_type} quantity at index {i}: {quantity}")

                converted_entries.append([price, quantity])

            except (ValueError, TypeError, IndexError) as e:
                raise ValueError(f"Error converting {entry_type} entry at index {i}: {e}")

        return converted_entries

    @staticmethod
    def validate_message_format(msg: Dict[str, Any], message_type: str) -> bool:
        """
        Validate Coins.xyz message format.

        Args:
            msg: Message to validate
            message_type: "snapshot", "diff", or "trade"

        Returns:
            True if format is valid, False otherwise
        """
        try:
            if message_type == "snapshot":
                return (
                    "lastUpdateId" in msg and
                    "bids" in msg and
                    "asks" in msg and
                    isinstance(msg["bids"], list) and
                    isinstance(msg["asks"], list)
                )

            elif message_type == "diff":
                data = msg.get("data", msg)
                return (
                    ("u" in data or "lastUpdateId" in data) and
                    ("b" in data or "bids" in data) and
                    ("a" in data or "asks" in data)
                )

            elif message_type == "trade":
                data = msg.get("data", msg)
                return (
                    "t" in data and  # trade id
                    "p" in data and  # price
                    "q" in data      # quantity
                )

            return False

        except (KeyError, TypeError):
            return False

    @staticmethod
    def extract_trading_pair_from_stream(stream: str) -> Optional[str]:
        """
        Extract trading pair from Coins.xyz WebSocket stream name.

        Examples:
        - "btcusdt@depth" -> "BTC-USDT"
        - "ethusdt@trade" -> "ETH-USDT"

        Args:
            stream: WebSocket stream name

        Returns:
            Trading pair in Hummingbot format or None if invalid
        """
        try:
            if "@" not in stream:
                return None

            symbol = stream.split("@")[0].upper()

            # Convert common symbols to Hummingbot format
            # This is a simplified conversion - in production, use exchange info
            if symbol.endswith("USDT"):
                base = symbol[:-4]
                return f"{base}-USDT"
            elif symbol.endswith("BTC"):
                base = symbol[:-3]
                return f"{base}-BTC"
            elif symbol.endswith("ETH"):
                base = symbol[:-3]
                return f"{base}-ETH"

            return None

        except (AttributeError, IndexError):
            return None

    @staticmethod
    def create_empty_snapshot(trading_pair: str, timestamp: Optional[float] = None) -> OrderBookMessage:
        """
        Create an empty order book snapshot message.

        Args:
            trading_pair: Trading pair in Hummingbot format
            timestamp: Message timestamp (defaults to current time)

        Returns:
            Empty OrderBookMessage snapshot
        """
        if timestamp is None:
            timestamp = time.time() * 1000

        content = {
            "trading_pair": trading_pair,
            "update_id": 0,
            "bids": [],
            "asks": []
        }

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp)


# Utility functions for common operations
def convert_coins_xyz_symbol_to_hummingbot(symbol: str) -> str:
    """
    Convert Coins.xyz symbol to Hummingbot trading pair format.

    Args:
        symbol: Coins.xyz symbol (e.g., "BTCUSDT")

    Returns:
        Hummingbot trading pair (e.g., "BTC-USDT")
    """
    # This is a simplified conversion - in production, use exchange info mapping
    common_quotes = ["USDT", "BTC", "ETH", "BNB", "BUSD"]

    for quote in common_quotes:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            return f"{base}-{quote}"

    # Fallback: assume last 4 characters are quote currency
    if len(symbol) > 4:
        base = symbol[:-4]
        quote = symbol[-4:]
        return f"{base}-{quote}"

    return symbol


def convert_hummingbot_to_coins_xyz_symbol(trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair to Coins.xyz symbol format.

    Args:
        trading_pair: Hummingbot trading pair (e.g., "BTC-USDT")

    Returns:
        Coins.xyz symbol (e.g., "BTCUSDT")
    """
    return trading_pair.replace("-", "").upper()


def is_valid_order_book_entry(entry: List) -> bool:
    """
    Validate order book entry format.

    Args:
        entry: Order book entry [price, quantity]

    Returns:
        True if valid, False otherwise
    """
    try:
        if not isinstance(entry, list) or len(entry) != 2:
            return False

        price, quantity = entry

        # Validate that values can be converted to Decimal
        price_decimal = Decimal(str(price))
        quantity_decimal = Decimal(str(quantity))

        # Validate ranges
        return price_decimal > 0 and quantity_decimal >= 0

    except (ValueError, TypeError, IndexError, Exception):
        return False


class OrderBookMessageConverter:
    """
    Advanced converter for order book messages with caching and optimization.
    """

    def __init__(self):
        """Initialize converter with symbol mapping cache."""
        self._symbol_cache: Dict[str, str] = {}
        self._reverse_symbol_cache: Dict[str, str] = {}

    def cache_symbol_mapping(self, hummingbot_pair: str, exchange_symbol: str) -> None:
        """
        Cache symbol mapping for faster conversion.

        Args:
            hummingbot_pair: Hummingbot format (e.g., "BTC-USDT")
            exchange_symbol: Exchange format (e.g., "BTCUSDT")
        """
        self._symbol_cache[hummingbot_pair] = exchange_symbol
        self._reverse_symbol_cache[exchange_symbol] = hummingbot_pair

    def convert_to_exchange_symbol(self, trading_pair: str) -> str:
        """
        Convert with caching support.

        Args:
            trading_pair: Hummingbot trading pair

        Returns:
            Exchange symbol
        """
        if trading_pair in self._symbol_cache:
            return self._symbol_cache[trading_pair]

        symbol = convert_hummingbot_to_coins_xyz_symbol(trading_pair)
        self._symbol_cache[trading_pair] = symbol
        return symbol

    def convert_to_hummingbot_pair(self, exchange_symbol: str) -> str:
        """
        Convert with caching support.

        Args:
            exchange_symbol: Exchange symbol

        Returns:
            Hummingbot trading pair
        """
        if exchange_symbol in self._reverse_symbol_cache:
            return self._reverse_symbol_cache[exchange_symbol]

        pair = convert_coins_xyz_symbol_to_hummingbot(exchange_symbol)
        self._reverse_symbol_cache[exchange_symbol] = pair
        return pair

    def batch_convert_snapshot(
        self,
        messages: List[Dict[str, Any]],
        trading_pairs: List[str]
    ) -> List[OrderBookMessage]:
        """
        Convert multiple snapshot messages efficiently.

        Args:
            messages: List of raw exchange messages
            trading_pairs: Corresponding trading pairs

        Returns:
            List of converted OrderBookMessage objects
        """
        converted_messages = []

        for msg, trading_pair in zip(messages, trading_pairs):
            try:
                converted_msg = CoinsxyzOrderBookMessage.snapshot_message_from_exchange(
                    msg, trading_pair
                )
                converted_messages.append(converted_msg)
            except Exception as e:
                # Log error but continue processing other messages
                print(f"Error converting snapshot for {trading_pair}: {e}")
                continue

        return converted_messages

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "symbol_cache_size": len(self._symbol_cache),
            "reverse_cache_size": len(self._reverse_symbol_cache)
        }


def merge_order_book_updates(
    base_snapshot: OrderBookMessage,
    updates: List[OrderBookMessage]
) -> OrderBookMessage:
    """
    Merge order book updates into a base snapshot.

    Args:
        base_snapshot: Base order book snapshot
        updates: List of order book diff messages

    Returns:
        Updated OrderBookMessage snapshot
    """
    if base_snapshot.type != OrderBookMessageType.SNAPSHOT:
        raise ValueError("Base message must be a snapshot")

    # Start with base snapshot data
    merged_bids = {price: qty for price, qty in base_snapshot.bids}
    merged_asks = {price: qty for price, qty in base_snapshot.asks}
    latest_update_id = base_snapshot.update_id

    # Apply updates in sequence
    for update in updates:
        if update.type != OrderBookMessageType.DIFF:
            continue

        # Update bids
        for price, qty in update.bids:
            if qty == 0:
                merged_bids.pop(price, None)  # Remove level
            else:
                merged_bids[price] = qty  # Update level

        # Update asks
        for price, qty in update.asks:
            if qty == 0:
                merged_asks.pop(price, None)  # Remove level
            else:
                merged_asks[price] = qty  # Update level

        # Update sequence ID
        if update.update_id > latest_update_id:
            latest_update_id = update.update_id

    # Convert back to list format, sorted by price
    final_bids = [[price, qty] for price, qty in sorted(merged_bids.items(), reverse=True)]
    final_asks = [[price, qty] for price, qty in sorted(merged_asks.items())]

    # Create merged snapshot
    content = {
        "trading_pair": base_snapshot.trading_pair,
        "update_id": latest_update_id,
        "bids": final_bids,
        "asks": final_asks
    }

    return OrderBookMessage(
        OrderBookMessageType.SNAPSHOT,
        content,
        time.time() * 1000
    )
