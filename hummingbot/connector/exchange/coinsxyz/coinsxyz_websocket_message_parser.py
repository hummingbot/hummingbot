"""
WebSocket Message Parser and Validation Framework for Coins.xyz Exchange.

This module provides comprehensive WebSocket message parsing and validation
with support for all market data stream types.
"""

import logging
import time
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.core.data_type.common import TradeType
from hummingbot.logger import HummingbotLogger


class MessageType(Enum):
    """WebSocket message types."""
    ORDER_BOOK_DIFF = "depthUpdate"
    TRADE = "trade"
    TICKER = "24hrTicker"
    KLINE = "kline"
    SUBSCRIPTION_RESPONSE = "subscription"
    ERROR = "error"
    UNKNOWN = "unknown"


class CoinsxyzWebSocketMessageParser:
    """
    WebSocket message parser and validation framework.

    Provides comprehensive parsing and validation for all Coins.xyz WebSocket
    message types with proper error handling and data normalization.
    """

    def __init__(self):
        """Initialize message parser."""
        self._logger = None

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def parse_message(self, raw_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse raw WebSocket message and determine its type.

        Args:
            raw_message: Raw WebSocket message data

        Returns:
            Parsed message with type information or None if invalid
        """
        try:
            if not isinstance(raw_message, dict):
                self.logger().warning(f"Invalid message format: {type(raw_message)}")
                return None

            # Determine message type
            message_type = self._determine_message_type(raw_message)

            # Parse based on message type
            if message_type == MessageType.ORDER_BOOK_DIFF:
                return self._parse_order_book_diff(raw_message)
            elif message_type == MessageType.TRADE:
                return self._parse_trade_message(raw_message)
            elif message_type == MessageType.TICKER:
                return self._parse_ticker_message(raw_message)
            elif message_type == MessageType.KLINE:
                return self._parse_kline_message(raw_message)
            elif message_type == MessageType.SUBSCRIPTION_RESPONSE:
                return self._parse_subscription_response(raw_message)
            elif message_type == MessageType.ERROR:
                return self._parse_error_message(raw_message)
            else:
                self.logger().debug(f"Unknown message type: {raw_message}")
                return None

        except Exception as e:
            self.logger().error(f"Error parsing WebSocket message: {e}")
            self.logger().debug(f"Raw message: {raw_message}")
            return None

    def _determine_message_type(self, message: Dict[str, Any]) -> MessageType:
        """
        Determine the type of WebSocket message.

        Args:
            message: WebSocket message data

        Returns:
            Message type enum
        """
        # Check for stream-based messages
        stream = message.get("stream", "")
        if stream:
            if "@depth" in stream:
                return MessageType.ORDER_BOOK_DIFF
            elif "@trade" in stream:
                return MessageType.TRADE
            elif "@ticker" in stream:
                return MessageType.TICKER
            elif "@kline" in stream:
                return MessageType.KLINE

        # Check for data-based message identification
        data = message.get("data", {})
        if isinstance(data, dict):
            event_type = data.get("e", "")
            if event_type == CONSTANTS.DIFF_EVENT_TYPE:
                return MessageType.ORDER_BOOK_DIFF
            elif event_type == CONSTANTS.TRADE_EVENT_TYPE:
                return MessageType.TRADE
            elif event_type == "24hrTicker":
                return MessageType.TICKER
            elif event_type == "kline":
                return MessageType.KLINE

        # Check for subscription responses
        if "result" in message or "id" in message:
            return MessageType.SUBSCRIPTION_RESPONSE

        # Check for error messages
        if "error" in message and message.get("error") is not None:
            return MessageType.ERROR

        return MessageType.UNKNOWN

    def _parse_order_book_diff(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse order book diff message.

        Expected format:
        {
            "stream": "btcusdt@depth",
            "data": {
                "e": "depthUpdate",
                "E": 1756794120409,
                "s": "BTCUSDT",
                "U": 123456,
                "u": 123457,
                "b": [["50000.00", "1.0"], ["49999.00", "0.0"]],
                "a": [["50001.00", "0.5"], ["50002.00", "2.0"]]
            }
        }
        """
        try:
            data = message.get("data", {})
            stream = message.get("stream", "")

            # Extract trading pair from stream
            if "@depth" in stream:
                symbol = stream.split("@")[0].upper()
            else:
                symbol = data.get("s", "")

            if not symbol:
                self.logger().warning("No symbol found in order book diff message")
                return None

            # Validate required fields
            bids = data.get("b", [])
            asks = data.get("a", [])
            update_id = data.get("u", data.get("U", 0))
            timestamp = data.get("E", int(time.time() * 1000))

            # Validate bid/ask data
            validated_bids = self._validate_order_book_entries(bids, "bids")
            validated_asks = self._validate_order_book_entries(asks, "asks")

            return {
                "type": MessageType.ORDER_BOOK_DIFF,
                "symbol": symbol,
                "update_id": update_id,
                "timestamp": timestamp / 1000.0,  # Convert to seconds
                "bids": validated_bids,
                "asks": validated_asks,
                "raw_message": message
            }

        except Exception as e:
            self.logger().error(f"Error parsing order book diff: {e}")
            return None

    def _parse_trade_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse trade message.

        Expected format:
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
        """
        try:
            data = message.get("data", {})
            stream = message.get("stream", "")

            # Extract trading pair from stream
            if "@trade" in stream:
                symbol = stream.split("@")[0].upper()
            else:
                symbol = data.get("s", "")

            if not symbol:
                self.logger().warning("No symbol found in trade message")
                return None

            # Extract trade data
            trade_id = str(data.get("t", data.get("id", 0)))
            price = str(data.get("p", data.get("price", "0")))
            quantity = str(data.get("q", data.get("qty", "0")))
            timestamp = float(data.get("T", data.get("time", data.get("E", 0))))
            is_buyer_maker = data.get("m", data.get("isBuyerMaker", False))

            # Convert timestamp from milliseconds to seconds if needed
            if timestamp > 1e12:
                timestamp = timestamp / 1000.0

            # Validate trade data
            if not self._validate_trade_data(price, quantity, trade_id):
                return None

            # Determine trade type (from taker perspective)
            trade_type = float(TradeType.SELL.value) if is_buyer_maker else float(TradeType.BUY.value)

            return {
                "type": MessageType.TRADE,
                "symbol": symbol,
                "trade_id": trade_id,
                "price": price,
                "quantity": quantity,
                "timestamp": timestamp,
                "trade_type": trade_type,
                "is_buyer_maker": is_buyer_maker,
                "raw_message": message
            }

        except Exception as e:
            self.logger().error(f"Error parsing trade message: {e}")
            return None

    def _parse_ticker_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse ticker message.

        Expected format:
        {
            "stream": "btcusdt@ticker",
            "data": {
                "e": "24hrTicker",
                "E": 1756794120409,
                "s": "BTCUSDT",
                "p": "500.00",
                "P": "1.01",
                "c": "50000.00",
                "v": "1000.5",
                "h": "51000.00",
                "l": "49000.00"
            }
        }
        """
        try:
            data = message.get("data", {})
            stream = message.get("stream", "")

            # Extract trading pair from stream
            if "@ticker" in stream:
                symbol = stream.split("@")[0].upper()
            else:
                symbol = data.get("s", "")

            if not symbol:
                self.logger().warning("No symbol found in ticker message")
                return None

            # Extract ticker data
            price_change = str(data.get("p", "0"))
            price_change_percent = str(data.get("P", "0"))
            last_price = str(data.get("c", "0"))
            volume = str(data.get("v", "0"))
            high_price = str(data.get("h", "0"))
            low_price = str(data.get("l", "0"))
            timestamp = float(data.get("E", int(time.time() * 1000)))

            # Convert timestamp from milliseconds to seconds if needed
            if timestamp > 1e12:
                timestamp = timestamp / 1000.0

            return {
                "type": MessageType.TICKER,
                "symbol": symbol,
                "last_price": last_price,
                "price_change": price_change,
                "price_change_percent": price_change_percent,
                "volume": volume,
                "high_price": high_price,
                "low_price": low_price,
                "timestamp": timestamp,
                "raw_message": message
            }

        except Exception as e:
            self.logger().error(f"Error parsing ticker message: {e}")
            return None

    def _parse_kline_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse kline/candlestick message.

        Expected format:
        {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "E": 1756794120409,
                "s": "BTCUSDT",
                "k": {
                    "t": 1640995200000,
                    "T": 1640995259999,
                    "s": "BTCUSDT",
                    "i": "1m",
                    "o": "50000.00",
                    "c": "50500.00",
                    "h": "51000.00",
                    "l": "49000.00",
                    "v": "100.5",
                    "n": 150
                }
            }
        }
        """
        try:
            data = message.get("data", {})
            stream = message.get("stream", "")
            kline_data = data.get("k", {})

            # Extract trading pair from stream
            if "@kline" in stream:
                symbol = stream.split("@")[0].upper()
                interval = stream.split("_")[-1] if "_" in stream else "1m"
            else:
                symbol = kline_data.get("s", "")
                interval = kline_data.get("i", "1m")

            if not symbol:
                self.logger().warning("No symbol found in kline message")
                return None

            # Extract kline data
            open_time = int(kline_data.get("t", 0))
            close_time = int(kline_data.get("T", 0))
            open_price = str(kline_data.get("o", "0"))
            close_price = str(kline_data.get("c", "0"))
            high_price = str(kline_data.get("h", "0"))
            low_price = str(kline_data.get("l", "0"))
            volume = str(kline_data.get("v", "0"))
            trade_count = int(kline_data.get("n", 0))

            return {
                "type": MessageType.KLINE,
                "symbol": symbol,
                "interval": interval,
                "open_time": open_time,
                "close_time": close_time,
                "open_price": open_price,
                "close_price": close_price,
                "high_price": high_price,
                "low_price": low_price,
                "volume": volume,
                "trade_count": trade_count,
                "timestamp": close_time / 1000.0,
                "raw_message": message
            }

        except Exception as e:
            self.logger().error(f"Error parsing kline message: {e}")
            return None

    def _parse_subscription_response(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse subscription response message.

        Expected format:
        {
            "result": null,
            "id": 1
        }
        """
        try:
            return {
                "type": MessageType.SUBSCRIPTION_RESPONSE,
                "id": message.get("id"),
                "result": message.get("result"),
                "raw_message": message
            }
        except Exception as e:
            self.logger().error(f"Error parsing subscription response: {e}")
            return None

    def _parse_error_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse error message.

        Expected format:
        {
            "error": {
                "code": -1,
                "msg": "Error message"
            },
            "id": 1
        }
        """
        try:
            error = message.get("error", {})
            return {
                "type": MessageType.ERROR,
                "id": message.get("id"),
                "error_code": error.get("code"),
                "error_message": error.get("msg"),
                "raw_message": message
            }
        except Exception as e:
            self.logger().error(f"Error parsing error message: {e}")
            return None

    def _validate_order_book_entries(self, entries: List[List[str]], entry_type: str) -> List[List[str]]:
        """
        Validate order book entries (bids/asks).

        Args:
            entries: List of [price, quantity] pairs
            entry_type: "bids" or "asks" for logging

        Returns:
            Validated entries list
        """
        validated_entries = []

        for entry in entries:
            try:
                if not isinstance(entry, list) or len(entry) < 2:
                    continue

                price = str(entry[0])
                quantity = str(entry[1])

                # Validate price and quantity
                if float(price) <= 0:
                    continue

                if float(quantity) < 0:
                    continue

                validated_entries.append([price, quantity])

            except (ValueError, IndexError) as e:
                self.logger().warning(f"Invalid {entry_type} entry: {entry}, error: {e}")
                continue

        return validated_entries

    def _validate_trade_data(self, price: str, quantity: str, trade_id: str) -> bool:
        """
        Validate trade data.

        Args:
            price: Trade price
            quantity: Trade quantity
            trade_id: Trade ID

        Returns:
            True if valid, False otherwise
        """
        try:
            if not trade_id or trade_id == "0":
                return False

            if float(price) <= 0:
                return False

            if float(quantity) <= 0:
                return False

            return True

        except ValueError:
            return False

    # Day 17: User Stream Message Parsing Methods

    def parse_user_stream_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse user stream message - Day 17 Implementation.

        Handles all user-specific messages including balance updates,
        order updates, and trade executions.

        Args:
            message: Raw user stream message

        Returns:
            Parsed message data or None if parsing failed
        """
        try:
            if not isinstance(message, dict):
                return None

            # Check for different user stream message types
            if 'outboundAccountPosition' in message:
                return self._parse_balance_update(message)
            elif 'executionReport' in message:
                return self._parse_order_update(message)
            elif 'trade' in message:
                return self._parse_trade_update(message)
            else:
                self.logger().debug(f"Unknown user stream message type: {message}")
                return None

        except Exception as e:
            self.logger().error(f"Error parsing user stream message: {e}")
            return None

    def _parse_balance_update(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse balance update message - Day 17 Implementation.

        Args:
            message: Balance update message

        Returns:
            Parsed balance update data
        """
        try:
            balance_data = message.get('outboundAccountPosition', {})

            return {
                'type': 'balance_update',
                'timestamp': message.get('E', int(time.time() * 1000)),
                'balances': [
                    {
                        'asset': balance.get('a'),
                        'free': Decimal(balance.get('f', '0')),
                        'locked': Decimal(balance.get('l', '0'))
                    }
                    for balance in balance_data.get('B', [])
                ]
            }

        except Exception as e:
            self.logger().error(f"Error parsing balance update: {e}")
            return None

    def _parse_order_update(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse order update message - Day 17 Implementation.

        Args:
            message: Order update message

        Returns:
            Parsed order update data
        """
        try:
            order_data = message.get('executionReport', {})

            return {
                'type': 'order_update',
                'timestamp': message.get('E', int(time.time() * 1000)),
                'order_id': order_data.get('i'),
                'client_order_id': order_data.get('c'),
                'symbol': order_data.get('s'),
                'side': order_data.get('S'),
                'order_type': order_data.get('o'),
                'status': order_data.get('X'),
                'quantity': Decimal(order_data.get('q', '0')),
                'price': Decimal(order_data.get('p', '0')),
                'executed_quantity': Decimal(order_data.get('z', '0')),
                'cumulative_quote_quantity': Decimal(order_data.get('Z', '0'))
            }

        except Exception as e:
            self.logger().error(f"Error parsing order update: {e}")
            return None

    def _parse_trade_update(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse trade execution message - Day 17 Implementation.

        Args:
            message: Trade execution message

        Returns:
            Parsed trade execution data
        """
        try:
            trade_data = message.get('trade', {})

            return {
                'type': 'trade_update',
                'timestamp': message.get('E', int(time.time() * 1000)),
                'trade_id': trade_data.get('t'),
                'order_id': trade_data.get('i'),
                'symbol': trade_data.get('s'),
                'side': trade_data.get('S'),
                'quantity': Decimal(trade_data.get('q', '0')),
                'price': Decimal(trade_data.get('p', '0')),
                'commission': Decimal(trade_data.get('n', '0')),
                'commission_asset': trade_data.get('N')
            }

        except Exception as e:
            self.logger().error(f"Error parsing trade update: {e}")
            return None

    def _process_balance_event(self, balance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process balance event data - Day 17 Implementation.

        Args:
            balance_data: Raw balance event data

        Returns:
            Processed balance event
        """
        try:
            return {
                'event_type': 'balance_update',
                'timestamp': balance_data.get('timestamp', int(time.time() * 1000)),
                'balances': balance_data.get('balances', []),
                'processed_at': int(time.time() * 1000)
            }
        except Exception as e:
            self.logger().error(f"Error processing balance event: {e}")
            return {}

    def _process_order_event(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process order event data - Day 17 Implementation.

        Args:
            order_data: Raw order event data

        Returns:
            Processed order event
        """
        try:
            return {
                'event_type': 'order_update',
                'timestamp': order_data.get('timestamp', int(time.time() * 1000)),
                'order_id': order_data.get('order_id'),
                'status': order_data.get('status'),
                'processed_at': int(time.time() * 1000)
            }
        except Exception as e:
            self.logger().error(f"Error processing order event: {e}")
            return {}

    def _process_trade_event(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process trade event data - Day 17 Implementation.

        Args:
            trade_data: Raw trade event data

        Returns:
            Processed trade event
        """
        try:
            return {
                'event_type': 'trade_execution',
                'timestamp': trade_data.get('timestamp', int(time.time() * 1000)),
                'trade_id': trade_data.get('trade_id'),
                'quantity': trade_data.get('quantity'),
                'price': trade_data.get('price'),
                'processed_at': int(time.time() * 1000)
            }
        except Exception as e:
            self.logger().error(f"Error processing trade event: {e}")
            return {}
