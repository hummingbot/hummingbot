import asyncio
import aiohttp

from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import \
    AscendExAPIOrderBookDataSource
from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book_tracker import AscendExOrderBookTracker
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class AscendExOrderBookTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.session = None
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker = AscendExOrderBookTracker(shared_client=self.session, throttler=self.throttler, trading_pairs=["BTC-USDT"])
        self.mock_data_source = AsyncMock()
        self.tracker._data_source = self.mock_data_source

    def tearDown(self) -> None:
        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def do_listen_stream_trade(self, ws_connect_mock):
        ret = {}

        self.tracker._shared_client = aiohttp.ClientSession()

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.tracker.start()
        await asyncio.sleep(0.5)

        ret["listen_for_order_book_snapshots called"] = self.mock_data_source.listen_for_order_book_snapshots.called
        ret["listen_for_trades"] = await self.mock_data_source.listen_for_trades()

        self.tracker.stop()

        ret["_order_book_stream_listener_task"] = self.tracker._order_book_stream_listener_task
        ret["_order_book_trade_listener_task"] = self.tracker._order_book_trade_listener_task

        await self.tracker._shared_client.close()

        return ret

    def test_tracker_listens_to_subscriptions_and_process_instruments_updates_when_starting(self):
        ret = asyncio.get_event_loop().run_until_complete(self.do_listen_stream_trade())

        self.assertTrue(ret["listen_for_order_book_snapshots called"])
        self.assertTrue(ret["listen_for_trades"])

        self.assertIsNone(ret["_order_book_stream_listener_task"])
        self.assertIsNone(ret["_order_book_trade_listener_task"])
