import asyncio

from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import \
    AscendExAPIOrderBookDataSource
from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book_tracker import AscendExOrderBookTracker
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class AscendExOrderBookTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.mocking_assistant = NetworkMockingAssistant()
        self.session = None
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker = AscendExOrderBookTracker(shared_client=self.session, throttler=self.throttler, trading_pairs=["BTC-USDT"])
        self.mock_data_source = AsyncMock()
        self.tracker._data_source = self.mock_data_source

    def tearDown(self) -> None:
        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()
