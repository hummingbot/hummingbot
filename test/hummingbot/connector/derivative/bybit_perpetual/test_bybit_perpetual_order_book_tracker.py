import asyncio

import aiohttp
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book_tracker import BybitPerpetualOrderBookTracker


class BybitPerpetualOrderBookTrackerTests(TestCase):

    def setUp(self) -> None:
        self.mock_data_source = AsyncMock()
        self.tracker = BybitPerpetualOrderBookTracker(aiohttp.ClientSession(), ["BTC-USDT"])
        self.tracker._data_source = self.mock_data_source

    def test_tracker_listens_to_subscriptions_and_process_instruments_updates_when_starting(self):
        self.tracker.start()
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self.mock_data_source.listen_for_subscriptions.called)
        self.assertTrue(self.mock_data_source.listen_for_instruments_info())

        self.tracker.stop()

        self.assertIsNone(self.tracker._order_book_event_listener_task)
        self.assertIsNone(self.tracker._order_book_instruments_info_listener_task)

        self.assertTrue(self.mock_data_source.order_book_create_function.called)
