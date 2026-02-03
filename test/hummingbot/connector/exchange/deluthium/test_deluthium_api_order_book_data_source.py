"""
Unit tests for Deluthium order book data source.

QA Test Plan Coverage:
- HB-CRIT-003: Order book data quality verification
- HB-HIGH-002: Bid/ask spread validation (bid < ask)
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.deluthium import deluthium_constants as CONSTANTS
from hummingbot.connector.exchange.deluthium.deluthium_api_order_book_data_source import (
    DeluthiumAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.deluthium.deluthium_order_book import DeluthiumOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestDeluthiumOrderBook(unittest.TestCase):
    """Test cases for DeluthiumOrderBook class."""

    def test_snapshot_message_from_exchange(self):
        """Test creating snapshot message from exchange data."""
        msg = {
            "trading_pair": "WBNB/USDT",
            "update_id": 1234567890,
            "bids": [[500.0, 1.0]],
            "asks": [[501.0, 1.0]],
        }
        
        result = DeluthiumOrderBook.snapshot_message_from_exchange(
            msg,
            timestamp=1234567.890
        )
        
        self.assertEqual(result.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(result.content["trading_pair"], "WBNB/USDT")
        self.assertEqual(result.content["bids"], [[500.0, 1.0]])
        self.assertEqual(result.content["asks"], [[501.0, 1.0]])

    def test_diff_message_from_exchange(self):
        """Test creating diff message from exchange data."""
        msg = {
            "trading_pair": "WBNB/USDT",
            "update_id": 1234567891,
            "bids": [[499.0, 2.0]],
            "asks": [[502.0, 2.0]],
        }
        
        result = DeluthiumOrderBook.diff_message_from_exchange(
            msg,
            timestamp=1234567.891
        )
        
        self.assertEqual(result.type, OrderBookMessageType.DIFF)
        self.assertEqual(result.content["trading_pair"], "WBNB/USDT")

    def test_trade_message_from_exchange(self):
        """Test creating trade message from exchange data."""
        msg = {
            "trading_pair": "WBNB/USDT",
            "side": "buy",
            "trade_id": "trade_123",
            "price": 500.0,
            "amount": 1.5,
            "timestamp": 1234567.890,
        }
        
        result = DeluthiumOrderBook.trade_message_from_exchange(msg)
        
        self.assertEqual(result.type, OrderBookMessageType.TRADE)
        self.assertEqual(result.content["trading_pair"], "WBNB/USDT")
        self.assertEqual(result.content["trade_id"], "trade_123")
        self.assertEqual(result.content["price"], 500.0)
        self.assertEqual(result.content["amount"], 1.5)


class TestDeluthiumAPIOrderBookDataSource(unittest.IsolatedAsyncioTestCase):
    """Async test cases for DeluthiumAPIOrderBookDataSource."""

    def setUp(self):
        """Set up test fixtures."""
        self.trading_pairs = ["WBNB/USDT"]
        
        # Mock the connector with chain-qualified cache
        self.connector = MagicMock()
        self.connector.pair_id_cache = {
            "WBNB/USDT:56": {
                "pair_id": "101",
                "chain_id": 56,
            }
        }
        self.connector._chain_id = 56
        self.connector._get_pair_cache = MagicMock(return_value={
            "pair_id": "101",
            "chain_id": 56,
        })
        self.connector._api_get = AsyncMock()
        self.connector.load_markets = AsyncMock()
        
        # Mock API factory
        self.api_factory = MagicMock()
        
        self.data_source = DeluthiumAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_get_last_traded_prices(self):
        """Test getting last traded prices."""
        self.connector.get_last_traded_prices = AsyncMock(
            return_value={"WBNB/USDT": 500.0}
        )
        
        result = await self.data_source.get_last_traded_prices(
            trading_pairs=self.trading_pairs
        )
        
        self.assertEqual(result, {"WBNB/USDT": 500.0})

    async def test_request_order_book_snapshot_success(self):
        """Test requesting order book snapshot."""
        self.connector._api_get = AsyncMock(return_value={
            "code": 10000,
            "data": {
                "price": "500.0",
                "volume_base_24h": "1000",
            }
        })
        
        result = await self.data_source._request_order_book_snapshot("WBNB/USDT")
        
        self.assertIn("trading_pair", result)
        self.assertEqual(result["trading_pair"], "WBNB/USDT")

    async def test_request_order_book_snapshot_no_pair_id(self):
        """Test requesting snapshot when pair ID is not cached."""
        self.connector._get_pair_cache = MagicMock(return_value={})
        self.connector.load_markets = AsyncMock()
        
        result = await self.data_source._request_order_book_snapshot("UNKNOWN/PAIR")
        
        self.assertEqual(result["bids"], [])
        self.assertEqual(result["asks"], [])

    async def test_order_book_snapshot(self):
        """Test getting full order book snapshot."""
        self.connector._api_get = AsyncMock(return_value={
            "code": 10000,
            "data": {"price": "500.0"}
        })
        
        result = await self.data_source._order_book_snapshot("WBNB/USDT")
        
        self.assertEqual(result.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(result.content["trading_pair"], "WBNB/USDT")


class TestDeluthiumOrderBookCriticalBugs(unittest.IsolatedAsyncioTestCase):
    """
    Test cases for critical order book bugs identified in Staff Engineer review.
    
    HB-CRIT-003: Order book data is fake/placeholder
    HB-HIGH-002: Order book bid/ask are at same price
    """

    def setUp(self):
        """Set up test fixtures."""
        self.trading_pairs = ["WBNB/USDT"]
        
        self.connector = MagicMock()
        self.connector.pair_id_cache = {"WBNB/USDT:56": {"pair_id": "101", "chain_id": 56}}
        self.connector._chain_id = 56
        self.connector._get_pair_cache = MagicMock(return_value={"pair_id": "101", "chain_id": 56})
        self.connector._api_get = AsyncMock()
        self.connector.load_markets = AsyncMock()
        
        self.api_factory = MagicMock()
        
        self.data_source = DeluthiumAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_order_book_bid_less_than_ask(self):
        """HB-HIGH-002: Verify bid price is LESS than ask price."""
        self.connector._api_get = AsyncMock(return_value={
            "code": 10000,
            "data": {"price": "500.0", "volume_base_24h": "1000"}
        })
        
        result = await self.data_source._request_order_book_snapshot("WBNB/USDT")
        
        if result["bids"] and result["asks"]:
            bid_price = result["bids"][0][0]
            ask_price = result["asks"][0][0]
            self.assertLess(bid_price, ask_price, f"Bid ({bid_price}) must be < Ask ({ask_price})")

    async def test_order_book_has_synthetic_flag(self):
        """HB-CRIT-003: Verify order book is marked as synthetic."""
        self.connector._api_get = AsyncMock(return_value={"code": 10000, "data": {"price": "500.0"}})
        
        result = await self.data_source._request_order_book_snapshot("WBNB/USDT")
        
        self.assertTrue(result.get("is_synthetic", False), "Order book should be flagged as synthetic")

    async def test_order_book_handles_api_error(self):
        """HB-CRIT-003: Verify order book handles API errors gracefully."""
        self.connector._api_get = AsyncMock(side_effect=Exception("API Error"))
        
        result = await self.data_source._request_order_book_snapshot("WBNB/USDT")
        
        self.assertEqual(result["bids"], [])
        self.assertEqual(result["asks"], [])


if __name__ == "__main__":
    unittest.main()
