"""
Comprehensive Mock WebSocket Responses for Coins.xyz Exchange Testing.

This module provides realistic mock WebSocket responses for all supported
message types including order book diffs, trades, tickers, and klines.
"""

import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MockMarketData:
    """Mock market data for generating realistic responses."""
    symbol: str
    base_price: float
    price_volatility: float = 0.02  # 2% volatility
    volume_base: float = 1000.0
    last_update_id: int = 1000000


class CoinsxyzMockWebSocketResponses:
    """
    Comprehensive mock WebSocket responses generator for Coins.xyz exchange.

    Provides realistic mock data for:
    - Order book diff messages
    - Trade messages
    - Ticker messages
    - Kline/candlestick messages
    - Subscription responses
    - Error messages
    """

    def __init__(self):
        """Initialize mock response generator."""
        self._market_data = {
            "BTCUSDT": MockMarketData("BTCUSDT", 50000.0, 0.03, 5000.0),
            "ETHUSDT": MockMarketData("ETHUSDT", 3000.0, 0.04, 3000.0),
            "ADAUSDT": MockMarketData("ADAUSDT", 0.5, 0.05, 10000.0),
            "DOTUSDT": MockMarketData("DOTUSDT", 25.0, 0.06, 2000.0),
            "LINKUSDT": MockMarketData("LINKUSDT", 15.0, 0.04, 1500.0),
        }
        self._trade_id_counter = 1000000
        self._subscription_id_counter = 1

    def get_order_book_diff_message(self,
                                    symbol: str = "BTCUSDT",
                                    num_bids: int = 5,
                                    num_asks: int = 5) -> Dict[str, Any]:
        """
        Generate realistic order book diff message.

        Args:
            symbol: Trading pair symbol
            num_bids: Number of bid levels
            num_asks: Number of ask levels

        Returns:
            Mock order book diff message
        """
        market_data = self._market_data.get(symbol, self._market_data["BTCUSDT"])
        current_price = self._get_current_price(market_data)

        # Generate realistic bid/ask levels
        bids = []
        asks = []

        # Generate bids (below current price)
        for i in range(num_bids):
            price_offset = (i + 1) * 0.001 * current_price  # 0.1% increments
            bid_price = current_price - price_offset
            quantity = random.uniform(0.1, 10.0)

            # Some entries with zero quantity (removals)
            if random.random() < 0.2:
                quantity = 0.0

            bids.append([f"{bid_price:.2f}", f"{quantity:.6f}"])

        # Generate asks (above current price)
        for i in range(num_asks):
            price_offset = (i + 1) * 0.001 * current_price  # 0.1% increments
            ask_price = current_price + price_offset
            quantity = random.uniform(0.1, 10.0)

            # Some entries with zero quantity (removals)
            if random.random() < 0.2:
                quantity = 0.0

            asks.append([f"{ask_price:.2f}", f"{quantity:.6f}"])

        market_data.last_update_id += 1

        return {
            "stream": f"{symbol.lower()}@depth",
            "data": {
                "e": "depthUpdate",
                "E": int(time.time() * 1000),
                "s": symbol,
                "U": market_data.last_update_id - 1,
                "u": market_data.last_update_id,
                "b": bids,
                "a": asks
            }
        }

    def get_trade_message(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Generate realistic trade message.

        Args:
            symbol: Trading pair symbol

        Returns:
            Mock trade message
        """
        market_data = self._market_data.get(symbol, self._market_data["BTCUSDT"])
        current_price = self._get_current_price(market_data)

        # Generate realistic trade data
        price_variation = random.uniform(-0.005, 0.005)  # ±0.5% price variation
        trade_price = current_price * (1 + price_variation)
        trade_quantity = random.uniform(0.001, 5.0)
        is_buyer_maker = random.choice([True, False])

        self._trade_id_counter += 1

        return {
            "stream": f"{symbol.lower()}@trade",
            "data": {
                "e": "trade",
                "E": int(time.time() * 1000),
                "s": symbol,
                "t": self._trade_id_counter,
                "p": f"{trade_price:.2f}",
                "q": f"{trade_quantity:.6f}",
                "b": random.randint(1000000, 9999999),  # buyer order id
                "a": random.randint(1000000, 9999999),  # seller order id
                "T": int(time.time() * 1000),
                "m": is_buyer_maker,
                "M": True  # ignore
            }
        }

    def get_ticker_message(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Generate realistic ticker message.

        Args:
            symbol: Trading pair symbol

        Returns:
            Mock ticker message
        """
        market_data = self._market_data.get(symbol, self._market_data["BTCUSDT"])
        current_price = self._get_current_price(market_data)

        # Generate 24hr statistics
        price_change_percent = random.uniform(-10.0, 10.0)
        price_change = current_price * (price_change_percent / 100)
        open_price = current_price - price_change

        high_price = current_price * random.uniform(1.0, 1.05)
        low_price = current_price * random.uniform(0.95, 1.0)
        volume = market_data.volume_base * random.uniform(0.5, 2.0)
        quote_volume = volume * current_price

        return {
            "stream": f"{symbol.lower()}@ticker",
            "data": {
                "e": "24hrTicker",
                "E": int(time.time() * 1000),
                "s": symbol,
                "p": f"{price_change:.2f}",
                "P": f"{price_change_percent:.2f}",
                "w": f"{current_price:.2f}",  # weighted average price
                "x": f"{open_price:.2f}",     # previous close
                "c": f"{current_price:.2f}",  # current close
                "Q": f"{random.uniform(0.1, 1.0):.6f}",  # close quantity
                "b": f"{current_price * 0.999:.2f}",     # best bid
                "B": f"{random.uniform(1.0, 10.0):.6f}",  # best bid quantity
                "a": f"{current_price * 1.001:.2f}",     # best ask
                "A": f"{random.uniform(1.0, 10.0):.6f}",  # best ask quantity
                "o": f"{open_price:.2f}",     # open price
                "h": f"{high_price:.2f}",     # high price
                "l": f"{low_price:.2f}",      # low price
                "v": f"{volume:.2f}",         # volume
                "q": f"{quote_volume:.2f}",   # quote volume
                "O": int((time.time() - 86400) * 1000),  # open time
                "C": int(time.time() * 1000),  # close time
                "F": random.randint(1000000, 9999999),    # first trade id
                "L": random.randint(1000000, 9999999),    # last trade id
                "n": random.randint(10000, 50000)         # trade count
            }
        }

    def get_kline_message(self,
                          symbol: str = "BTCUSDT",
                          interval: str = "1m") -> Dict[str, Any]:
        """
        Generate realistic kline/candlestick message.

        Args:
            symbol: Trading pair symbol
            interval: Kline interval

        Returns:
            Mock kline message
        """
        market_data = self._market_data.get(symbol, self._market_data["BTCUSDT"])
        current_price = self._get_current_price(market_data)

        # Generate OHLC data
        open_price = current_price * random.uniform(0.98, 1.02)
        close_price = current_price
        high_price = max(open_price, close_price) * random.uniform(1.0, 1.02)
        low_price = min(open_price, close_price) * random.uniform(0.98, 1.0)

        volume = market_data.volume_base * random.uniform(0.1, 2.0)
        quote_volume = volume * ((open_price + close_price) / 2)

        # Calculate time based on interval
        current_time = int(time.time() * 1000)
        interval_ms = self._get_interval_milliseconds(interval)
        open_time = (current_time // interval_ms) * interval_ms
        close_time = open_time + interval_ms - 1

        return {
            "stream": f"{symbol.lower()}@kline_{interval}",
            "data": {
                "e": "kline",
                "E": current_time,
                "s": symbol,
                "k": {
                    "t": open_time,           # open time
                    "T": close_time,          # close time
                    "s": symbol,              # symbol
                    "i": interval,            # interval
                    "f": random.randint(1000000, 9999999),  # first trade id
                    "L": random.randint(1000000, 9999999),  # last trade id
                    "o": f"{open_price:.2f}",   # open price
                    "c": f"{close_price:.2f}",  # close price
                    "h": f"{high_price:.2f}",   # high price
                    "l": f"{low_price:.2f}",    # low price
                    "v": f"{volume:.6f}",       # volume
                    "n": random.randint(100, 1000),        # trade count
                    "x": False,               # is kline closed
                    "q": f"{quote_volume:.2f}",             # quote volume
                    "V": f"{volume * 0.6:.6f}",             # taker buy volume
                    "Q": f"{quote_volume * 0.6:.2f}",       # taker buy quote volume
                    "B": "0"                  # ignore
                }
            }
        }

    def get_subscription_response(self,
                                  channels: List[str],
                                  success: bool = True) -> Dict[str, Any]:
        """
        Generate subscription response message.

        Args:
            channels: List of subscribed channels
            success: Whether subscription was successful

        Returns:
            Mock subscription response
        """
        self._subscription_id_counter += 1

        if success:
            return {
                "result": None,
                "id": self._subscription_id_counter
            }
        else:
            return {
                "error": {
                    "code": -2011,
                    "msg": "Unknown symbol."
                },
                "id": self._subscription_id_counter
            }

    def get_error_message(self,
                          error_code: int = -1,
                          error_msg: str = "Generic error") -> Dict[str, Any]:
        """
        Generate error message.

        Args:
            error_code: Error code
            error_msg: Error message

        Returns:
            Mock error message
        """
        return {
            "error": {
                "code": error_code,
                "msg": error_msg
            },
            "id": self._subscription_id_counter
        }

    def get_batch_messages(self,
                           symbol: str = "BTCUSDT",
                           count: int = 10) -> List[Dict[str, Any]]:
        """
        Generate batch of mixed message types for testing.

        Args:
            symbol: Trading pair symbol
            count: Number of messages to generate

        Returns:
            List of mock messages
        """
        messages = []
        message_types = ["trade", "ticker", "depth", "kline"]

        for _ in range(count):
            msg_type = random.choice(message_types)

            if msg_type == "trade":
                messages.append(self.get_trade_message(symbol))
            elif msg_type == "ticker":
                messages.append(self.get_ticker_message(symbol))
            elif msg_type == "depth":
                messages.append(self.get_order_book_diff_message(symbol))
            elif msg_type == "kline":
                messages.append(self.get_kline_message(symbol))

        return messages

    def _get_current_price(self, market_data: MockMarketData) -> float:
        """Get current price with volatility."""
        volatility = random.uniform(-market_data.price_volatility, market_data.price_volatility)
        return market_data.base_price * (1 + volatility)

    def _get_interval_milliseconds(self, interval: str) -> int:
        """Convert interval string to milliseconds."""
        interval_map = {
            "1m": 60 * 1000,
            "3m": 3 * 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
            "30m": 30 * 60 * 1000,
            "1h": 60 * 60 * 1000,
            "2h": 2 * 60 * 60 * 1000,
            "4h": 4 * 60 * 60 * 1000,
            "6h": 6 * 60 * 60 * 1000,
            "8h": 8 * 60 * 60 * 1000,
            "12h": 12 * 60 * 60 * 1000,
            "1d": 24 * 60 * 60 * 1000,
            "3d": 3 * 24 * 60 * 60 * 1000,
            "1w": 7 * 24 * 60 * 60 * 1000,
            "1M": 30 * 24 * 60 * 60 * 1000
        }
        return interval_map.get(interval, 60 * 1000)  # default to 1m

    def simulate_network_issues(self,
                                message: Dict[str, Any],
                                issue_type: str = "delay") -> Dict[str, Any]:
        """
        Simulate various network issues for testing.

        Args:
            message: Original message
            issue_type: Type of issue (delay, corruption, duplication)

        Returns:
            Modified message simulating network issues
        """
        if issue_type == "corruption":
            # Corrupt some data
            corrupted = message.copy()
            if "data" in corrupted and "p" in corrupted["data"]:
                corrupted["data"]["p"] = "invalid_price"
            return corrupted

        elif issue_type == "duplication":
            # Return the same message (caller should handle duplication)
            return message

        elif issue_type == "delay":
            # Add artificial delay timestamp
            delayed = message.copy()
            if "data" in delayed and "E" in delayed["data"]:
                delayed["data"]["E"] = int((time.time() - 5) * 1000)  # 5 second delay
            return delayed

        return message
