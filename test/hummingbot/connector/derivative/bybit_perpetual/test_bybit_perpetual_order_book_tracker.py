import asyncio

from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import \
    BybitPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book_tracker import BybitPerpetualOrderBookTracker


class BybitPerpetualOrderBookTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mock_data_source = AsyncMock()
        self.tracker = BybitPerpetualOrderBookTracker(AsyncMock(), trading_pairs=["BTC-USDT"])
        self.tracker._data_source = self.mock_data_source

    def tearDown(self) -> None:
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def test_tracker_listens_to_subscriptions_and_process_instruments_updates_when_starting(self):
        self.tracker.start()
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self.mock_data_source.listen_for_subscriptions.called)
        self.assertTrue(self.mock_data_source.listen_for_instruments_info())

        self.tracker.stop()

        self.assertIsNone(self.tracker._order_book_event_listener_task)
        self.assertIsNone(self.tracker._order_book_instruments_info_listener_task)

    def test_trading_pair_symbol(self):
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        local_tracker = BybitPerpetualOrderBookTracker(AsyncMock(), ["BTC-USDT"])
        local_tracker._data_source = BybitPerpetualAPIOrderBookDataSource()
        symbol = asyncio.get_event_loop().run_until_complete(local_tracker.trading_pair_symbol("BTC-USDT"))

        self.assertEqual("BTCUSDT", symbol)
