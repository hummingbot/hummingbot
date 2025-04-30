import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource


class DummyOrderBook(OrderBook):
    def __init__(self):
        super().__init__()
        self.last_trade_price = 0
        # Add properties needed for testing
        self._last_applied_trade = 0
        self.last_trade_price_rest_updated = 0
        self.max_trade_interval = 10

    @property
    def last_applied_trade(self):
        return self._last_applied_trade

    # Allow setting for testing
    @last_applied_trade.setter
    def last_applied_trade(self, value):
        self._last_applied_trade = value


class DummyOrderBookTrackerDataSource(OrderBookTrackerDataSource):
    async def get_last_traded_prices(self, trading_pairs, domain=None):
        return {pair: 100.0 for pair in trading_pairs}

    async def get_new_order_book(self, trading_pair):
        return DummyOrderBook()

    async def listen_for_order_book_diffs(self, ev_loop, output):
        await asyncio.sleep(0.01)

    async def listen_for_trades(self, ev_loop, output):
        await asyncio.sleep(0.01)

    async def listen_for_order_book_snapshots(self, ev_loop, output):
        await asyncio.sleep(0.01)

    async def listen_for_subscriptions(self):
        await asyncio.sleep(0.01)


class TestOrderBookTrackerAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.data_source = DummyOrderBookTrackerDataSource(["BTC-USD"])
        self.tracker = OrderBookTracker(self.data_source, ["BTC-USD"])

    async def test_update_last_trade_prices_loop_same_price(self):
        """Test when the last price is the same as current price (should increase max_trade_interval)"""
        self.tracker._order_books["BTC-USD"] = DummyOrderBook()
        self.tracker._order_books_initialized.set()

        # Setup the order book to appear outdated
        order_book = self.tracker._order_books["BTC-USD"]
        order_book.last_applied_trade = 0
        order_book.last_trade_price_rest_updated = 0
        # Set last_trade_price to be the same as what will be returned from API
        order_book.last_trade_price = 100.0
        order_book.max_trade_interval = 10

        # Mock the sleep function and get_last_traded_prices
        self.data_source.get_last_traded_prices = AsyncMock(return_value={"BTC-USD": 100.0})

        # Use patch to replace the loop's sleep function and break after one iteration
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            with patch('time.perf_counter', return_value=1000):
                with self.assertRaises(asyncio.CancelledError):
                    await self.tracker._update_last_trade_prices_loop()

            # Verify that get_last_traded_prices was called
            self.data_source.get_last_traded_prices.assert_called_once()

            # Check that max_trade_interval was increased (multiplied by 2)
            self.assertEqual(order_book.max_trade_interval, 20)

    async def test_update_last_trade_prices_loop_different_price(self):
        """Test when the last price is different from current price (should reduce max_trade_interval)"""
        self.tracker._order_books["BTC-USD"] = DummyOrderBook()
        self.tracker._order_books_initialized.set()

        # Setup the order book to appear outdated
        order_book = self.tracker._order_books["BTC-USD"]
        order_book.last_applied_trade = 0
        order_book.last_trade_price_rest_updated = 0
        # Set last_trade_price to be different from what will be returned from API
        order_book.last_trade_price = 99.0
        order_book.max_trade_interval = 10

        # Mock the sleep function and get_last_traded_prices
        self.data_source.get_last_traded_prices = AsyncMock(return_value={"BTC-USD": 101.0})

        # Use patch to replace the loop's sleep function and break after one iteration
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            with patch('time.perf_counter', return_value=1000):
                with self.assertRaises(asyncio.CancelledError):
                    await self.tracker._update_last_trade_prices_loop()

            # Verify that get_last_traded_prices was called
            self.data_source.get_last_traded_prices.assert_called_once()

            # Check that last_trade_price was updated
            self.assertEqual(order_book.last_trade_price, 101.0)

            # Check that max_trade_interval was decreased (divided by 2, but with min of 5)
            self.assertEqual(order_book.max_trade_interval, 5)

    async def test_update_last_trade_prices_loop_with_domain(self):
        """Test the domain parameter path"""
        self.tracker._order_books["BTC-USD"] = DummyOrderBook()
        self.tracker._order_books_initialized.set()
        self.tracker._domain = "test_domain"

        # Setup the order book to appear outdated
        order_book = self.tracker._order_books["BTC-USD"]
        order_book.last_applied_trade = 0
        order_book.last_trade_price_rest_updated = 0

        # Mock the sleep function and get_last_traded_prices
        self.data_source.get_last_traded_prices = AsyncMock(return_value={"BTC-USD": 101.0})

        # Use patch to replace the loop's sleep function and break after one iteration
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            mock_sleep.side_effect = [None, asyncio.CancelledError()]

            with patch('time.perf_counter', return_value=1000):
                with self.assertRaises(asyncio.CancelledError):
                    await self.tracker._update_last_trade_prices_loop()

            # Verify that get_last_traded_prices was called with domain parameter
            self.data_source.get_last_traded_prices.assert_called_once_with(
                trading_pairs=["BTC-USD"], domain="test_domain")

    async def test_update_last_trade_prices_loop_exception_handling(self):
        """Test the exception handling path"""
        self.tracker._order_books["BTC-USD"] = DummyOrderBook()
        self.tracker._order_books_initialized.set()

        # Setup the order book to appear outdated
        order_book = self.tracker._order_books["BTC-USD"]
        order_book.last_applied_trade = 0
        order_book.last_trade_price_rest_updated = 0

        # Mock get_last_traded_prices to raise exception
        self.data_source.get_last_traded_prices = AsyncMock(side_effect=Exception("Test exception"))

        # Create a fresh logger mock for each test
        mock_logger = MagicMock()
        mock_network = MagicMock()
        mock_logger.return_value.network = mock_network

        # Replace the class logger method entirely
        original_logger = OrderBookTracker.logger
        OrderBookTracker.logger = mock_logger

        try:
            # Use a custom sleep function that raises CancelledError immediately after the exception
            # This prevents multiple loop iterations during the test
            async def custom_sleep(seconds=0):
                # When called with 30, it means we're in the exception handler
                if seconds == 30:
                    raise asyncio.CancelledError()

            with patch('asyncio.sleep', custom_sleep):
                with patch('time.perf_counter', return_value=1000):
                    with self.assertRaises(asyncio.CancelledError):
                        await self.tracker._update_last_trade_prices_loop()

            # Verify logger.network was called exactly once with the right arguments
            mock_network.assert_called_once_with(
                'Unexpected error while fetching last trade price.',
                exc_info=True
            )
        finally:
            # Restore the original logger method
            OrderBookTracker.logger = original_logger


if __name__ == "__main__":
    unittest.main()
