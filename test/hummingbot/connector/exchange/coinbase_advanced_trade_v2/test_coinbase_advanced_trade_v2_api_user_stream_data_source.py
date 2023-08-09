import asyncio
import contextlib
import functools
import random
import unittest
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade_v2 import coinbase_advanced_trade_v2_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_api_user_stream_data_source import (
    CoinbaseAdvancedTradeV2APIUserStreamDataSource,
    CoinbaseAdvancedTradeV2CumulativeUpdate,
    WSAssistantPtl,
    _MultiStreamDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.stream_data_source import StreamState, TaskState
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse


class MockWebAssistant(WSAssistantPtl):
    def __init__(self):
        self.send_args = None
        self.connect_args = None
        self.connect_count = 0
        self.disconnect_count = 0
        self.send_count = 0
        self.send_called = None
        self.receive_called = None
        self.disconnect_called = None
        self.connect_called = None

    async def connect(
            self,
            ws_url: str,
            *,
            ping_timeout: float,
            message_timeout: float | None = None,
            ws_headers: Dict | None = None,
    ) -> None:
        self.connect_called = True
        self.connect_args = {
            "ws_url": ws_url,
            "ping_timeout": ping_timeout,
            "message_timeout": message_timeout,
            "ws_headers": ws_headers
        }
        self.connect_count += 1

    async def disconnect(self) -> None:
        self.disconnect_called = True
        self.disconnect_count += 1

    async def receive(self) -> WSResponse | None:
        self.receive_called = True
        return None

    async def send(self, request: WSRequest) -> None:
        self.send_called = True
        self.send_args = request
        self.send_count += 1


class MockDataSource(CoinbaseAdvancedTradeV2APIUserStreamDataSource):
    async def _connected_websocket_assistant(self):
        return MockWebAssistant()

    async def _subscribe_channels(self, ws) -> None:
        pass


class CoinbaseAdvancedTradeV2APIUserStreamDataSourceTests(
    IsolatedAsyncioWrapperTestCase,
    LoggerMixinForTest,
):
    quote_asset = None
    base_asset = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.trading_pairs = ["COINALPHA-HBOT", "COINALPHA-TOBH"]
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.auth = MagicMock()
        self.channels = ("user", "channel0")
        self.trading_pairs = ("ETH-USD", "BTC-USD")
        self.ws_assistant = MockWebAssistant()
        self.partial_assistant = functools.partial(self.get_ws_assistant, self.ws_assistant)
        self.output_queue = asyncio.Queue()

        self.cumulative_update = CoinbaseAdvancedTradeV2CumulativeUpdate(
            exchange_order_id="123",
            client_order_id="456",
            status="done",
            trading_pair="ETH-USD",
            fill_timestamp=123456789,
            average_price=Decimal("123.456"),
            cumulative_base_amount=Decimal("123.456"),
            remainder_base_amount=Decimal("123.456"),
            cumulative_fee=Decimal("123.456"),
        )
        self.data_source = CoinbaseAdvancedTradeV2APIUserStreamDataSource(
            channels=self.channels,
            pairs=self.trading_pairs,
            ws_factory=self.partial_assistant,
            pair_to_symbol=self.pair_to_symbol,
            symbol_to_pair=self.symbol_to_pair,
            heartbeat_channel="heartbeat",
        )
        self.set_loggers([self.data_source.logger()])

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.resume_test_event = asyncio.Event()
        self.get_ws_assistant_count = 0

    async def asyncTearDown(self) -> None:
        await super().asyncTearDown()

    def tearDown(self) -> None:
        super().tearDown()

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    async def get_ws_assistant(self, ws_assistant):
        self.get_ws_assistant_called = True
        self.get_ws_assistant_args = ws_assistant
        self.get_ws_assistant_count += 1
        return ws_assistant

    async def pair_to_symbol(self, pair: str) -> str:
        self.pair_to_symbol_called = True
        self.pair_to_symbol_args = pair
        s0, s1 = pair.split("-")
        await asyncio.sleep(0)
        return f"{s0}:{s1}"

    async def symbol_to_pair(self, symbol: str) -> str:
        self.symbol_to_pair_called = True
        self.psymbol_to_pair_args = symbol
        s0, s1 = symbol.split(":")
        await asyncio.sleep(0)
        return f"{s0}-{s1}"

    def test_init(self):
        self.assertIsInstance(self.data_source._stream_to_queue, _MultiStreamDataSource, )
        self.assertEqual(4, len(self.data_source._stream_to_queue.states))
        self.assertTrue(
            all(s == (StreamState.CLOSED, TaskState.STOPPED) for s in self.data_source._stream_to_queue.states))
        self.assertEqual(0, self.ws_assistant.connect_count)

    async def test_listen_for_user_stream_mocked(self):
        with patch.object(self.data_source, "_stream_to_queue",
                          AsyncMock(spec=_MultiStreamDataSource)) as stream_to_queue_mock:
            side_effects = [self.cumulative_update for _ in range(random.randint(5, 10))]
            stream_to_queue_mock.queue.get = AsyncMock(side_effect=side_effects)

            with contextlib.suppress(StopAsyncIteration):
                await self.data_source.listen_for_user_stream(self.output_queue)

            stream_to_queue_mock.open.assert_called_once()
            stream_to_queue_mock.start_stream.assert_called_once()
            stream_to_queue_mock.subscribe.assert_called_once()
            # The number of calls to get should be the number of side effects + 1 for the StopAsyncIteration
            self.assertEqual(len(side_effects) + 1, stream_to_queue_mock.queue.get.call_count)
            # The number of calls to put should be the number of side effects
            self.assertEqual(len(side_effects), self.output_queue.qsize())

    async def test_listen_for_user_stream_mocked_open(self):
        self.assertTrue(
            all(s == (StreamState.CLOSED, TaskState.STOPPED) for s in self.data_source._stream_to_queue.states))
        open = self.data_source._stream_to_queue.open
        with patch.object(self.data_source, "_stream_to_queue",
                          AsyncMock(spec=_MultiStreamDataSource)) as stream_to_queue_mock:
            self.data_source._stream_to_queue.open = open
            side_effects = []
            stream_to_queue_mock.queue.get = AsyncMock(side_effect=side_effects)

            with contextlib.suppress(StopAsyncIteration):
                await self.data_source.listen_for_user_stream(self.output_queue)

            stream_to_queue_mock.start_stream.assert_called_once()
            stream_to_queue_mock.subscribe.assert_called_once()
            # The number of calls to get should be the number of side effects + 1 for the StopAsyncIteration
            self.assertEqual(len(side_effects) + 1, stream_to_queue_mock.queue.get.call_count)
            # The number of calls to put should be the number of side effects
            self.assertEqual(len(side_effects), self.output_queue.qsize())
        self.assertTrue(
            all(s == (StreamState.OPENED, TaskState.STOPPED) for s in self.data_source._stream_to_queue.states))
        self.assertEqual(4, self.get_ws_assistant_count)
        self.assertEqual(4, self.ws_assistant.connect_count)
        # 4 heartbeats
        self.assertEqual(4, self.ws_assistant.send_count)

    async def test_connected_websocket_assistant_connect_call(self):
        with self.assertRaises(NotImplementedError):
            await self.data_source._connected_websocket_assistant()

    async def test_subscribe_channels_send_call(self):
        with self.assertRaises(NotImplementedError):
            await self.data_source._subscribe_channels(self.ws_assistant)


if __name__ == '__main__':
    unittest.main()
