#!/usr/bin/env python
"""
Tests for OrderBookTrackerDataSource base class.

This module tests:
- add_trading_pair: Adds a trading pair to the internal list
- remove_trading_pair: Removes a trading pair from the internal list
"""
import unittest
from typing import Any, Dict, List, Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class MockOrderBookTrackerDataSource(OrderBookTrackerDataSource):
    """Concrete implementation of OrderBookTrackerDataSource for testing."""

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return {pair: 100.0 for pair in trading_pairs}

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        raise NotImplementedError

    async def _connected_websocket_assistant(self) -> WSAssistant:
        raise NotImplementedError

    async def _subscribe_channels(self, ws: WSAssistant):
        raise NotImplementedError

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        return ""

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        return True

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        return True


class OrderBookTrackerDataSourceTests(unittest.TestCase):
    """Tests for the OrderBookTrackerDataSource base class methods."""

    def setUp(self):
        self.trading_pairs = ["BTC-USDT", "ETH-USDT"]
        self.data_source = MockOrderBookTrackerDataSource(trading_pairs=self.trading_pairs.copy())

    def test_initial_trading_pairs(self):
        """Test that trading pairs are correctly initialized."""
        self.assertEqual(self.trading_pairs, self.data_source._trading_pairs)

    def test_add_trading_pair_new_pair(self):
        """Test adding a new trading pair."""
        new_pair = "SOL-USDT"

        self.assertNotIn(new_pair, self.data_source._trading_pairs)

        self.data_source.add_trading_pair(new_pair)

        self.assertIn(new_pair, self.data_source._trading_pairs)
        self.assertEqual(3, len(self.data_source._trading_pairs))

    def test_add_trading_pair_existing_pair(self):
        """Test that adding an existing pair doesn't create duplicates."""
        existing_pair = "BTC-USDT"

        self.assertIn(existing_pair, self.data_source._trading_pairs)
        initial_count = len(self.data_source._trading_pairs)

        self.data_source.add_trading_pair(existing_pair)

        # Should not create duplicate
        self.assertEqual(initial_count, len(self.data_source._trading_pairs))

    def test_remove_trading_pair_existing_pair(self):
        """Test removing an existing trading pair."""
        pair_to_remove = "BTC-USDT"

        self.assertIn(pair_to_remove, self.data_source._trading_pairs)

        self.data_source.remove_trading_pair(pair_to_remove)

        self.assertNotIn(pair_to_remove, self.data_source._trading_pairs)
        self.assertEqual(1, len(self.data_source._trading_pairs))

    def test_remove_trading_pair_nonexistent_pair(self):
        """Test that removing a nonexistent pair doesn't raise an error."""
        nonexistent_pair = "NONEXISTENT-PAIR"

        self.assertNotIn(nonexistent_pair, self.data_source._trading_pairs)
        initial_count = len(self.data_source._trading_pairs)

        # Should not raise
        self.data_source.remove_trading_pair(nonexistent_pair)

        # Count should remain the same
        self.assertEqual(initial_count, len(self.data_source._trading_pairs))

    def test_add_and_remove_trading_pair_sequence(self):
        """Test adding and removing trading pairs in sequence."""
        new_pair = "SOL-USDT"

        # Add new pair
        self.data_source.add_trading_pair(new_pair)
        self.assertIn(new_pair, self.data_source._trading_pairs)

        # Remove it
        self.data_source.remove_trading_pair(new_pair)
        self.assertNotIn(new_pair, self.data_source._trading_pairs)

        # Remove an original pair
        self.data_source.remove_trading_pair("BTC-USDT")
        self.assertNotIn("BTC-USDT", self.data_source._trading_pairs)

        # Only ETH-USDT should remain
        self.assertEqual(["ETH-USDT"], self.data_source._trading_pairs)

    def test_ws_assistant_initialization(self):
        """Test that ws_assistant is initially None."""
        self.assertIsNone(self.data_source._ws_assistant)

    def test_order_book_create_function(self):
        """Test that order_book_create_function returns OrderBook by default."""
        order_book = self.data_source.order_book_create_function()
        self.assertIsInstance(order_book, OrderBook)

    def test_order_book_create_function_setter(self):
        """Test setting a custom order_book_create_function."""
        class CustomOrderBook(OrderBook):
            pass

        self.data_source.order_book_create_function = lambda: CustomOrderBook()

        order_book = self.data_source.order_book_create_function()
        self.assertIsInstance(order_book, CustomOrderBook)
