import asyncio
import functools
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Any, Awaitable, Callable, Coroutine, Dict, List
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_api_user_stream_data_source import (
    WSAssistantPtl,
    _MultiStreamDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.pipeline import PipeBlock, PipesCollector
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.stream_data_source import (
    StreamAction,
    StreamDataSource,
    StreamState,
)
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.task_manager import TaskManager, TaskState
from hummingbot.core.web_assistant.connections.data_types import WSRequest


class MockWebAssistant(WSAssistantPtl):
    def __init__(self):
        self.send_args = None
        self.connect_args = None
        self.connect_count = 0
        self.disconnect_count = 0
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

    async def receive(self) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        self.receive_called = True

    async def send(self, request: WSRequest) -> None:
        self.send_called = True
        self.send_args = request


class TestStreamsDataSource(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    quote_asset = None
    base_asset = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "COINALPHA"
        self.quote_asset = "HBOT"
        self.channels = ("channel0", "channel1", "channel2")
        self.trading_pairs = ("COINALPHA-HBOT", "COINALPHA-TOBH")

        self.get_ws_assistant_called = False
        self.get_ws_assistant_args = None
        self.ws_assistant = MockWebAssistant()
        self.partial_assistant = functools.partial(self.get_ws_assistant, self.ws_assistant)
        self.heartbeat_channel = "heartbeats"
        self.streams_data_source = _MultiStreamDataSource(
            channels=self.channels,
            pairs=self.trading_pairs,
            ws_factory=self.partial_assistant,
            ws_url="ws://localhost:1234",
            pair_to_symbol=self.pair_to_symbol,
            symbol_to_pair=self.symbol_to_pair,
            subscription_builder=self.subscription_builder,
            heartbeat_channel=self.heartbeat_channel,
        )
        self.set_loggers([self.streams_data_source.logger(), StreamDataSource.logger()])

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.symbol = await self.pair_to_symbol(f"{self.base_asset}-{self.quote_asset}")
        # Reset the mock
        self.pair_to_symbol_called = False
        self.pair_to_symbol_args = None
        self.symbol_to_pair_called = False
        self.symbol_to_pair_args = None

    async def asyncTearDown(self) -> None:
        await self.streams_data_source.close()
        await super().asyncTearDown()

    async def get_ws_assistant(self, ws_assistant):
        self.get_ws_assistant_called = True
        self.get_ws_assistant_args = ws_assistant
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
        s0, s1 = symbol.split("-")
        await asyncio.sleep(0)
        return f"{s0}:{s1}"

    @staticmethod
    async def subscription_builder(
            *,
            action: StreamAction,
            channel: str,
            pair: str,
            pair_to_symbol: Callable[[str], Awaitable[str]]) -> Dict[str, Any]:
        if action == StreamAction.SUBSCRIBE:
            _type = "subscribe"
        elif action == StreamAction.UNSUBSCRIBE:
            _type = "unsubscribe"
        else:
            raise ValueError(f"Invalid action: {action}")
        return {
            "type": _type,
            "product_ids": [await pair_to_symbol(pair)],
            "channel": channel,
        }

    async def test__stream_keys(self):
        self.assertEqual("a:b", self.streams_data_source._stream_key(channel="a", pair="b"))

    async def test_initialization(self):
        # Streams
        self.assertTrue(all(self.streams_data_source._stream_key(channel=c, pair=p) in
                            self.streams_data_source._streams for c in self.channels for p in self.trading_pairs))
        self.assertTrue(all(isinstance(s, StreamDataSource) for s in self.streams_data_source._streams.values()))
        self.assertTrue(all(s._stream_state == StreamState.CLOSED for s in self.streams_data_source._streams.values()))
        self.assertTrue(all(s._task_state == TaskState.STOPPED for s in self.streams_data_source._streams.values()))

        # Transformers
        self.assertTrue(all(self.streams_data_source._stream_key(channel=c, pair=p) in
                            self.streams_data_source._transformers for c in self.channels for p in self.trading_pairs))
        self.assertTrue(all(isinstance(t, List) for t in self.streams_data_source._transformers.values()))
        self.assertTrue(all(len(t) == 2 for t in self.streams_data_source._transformers.values()))
        self.assertTrue(
            all(isinstance(p, PipeBlock) for t in self.streams_data_source._transformers.values() for p in t))

        # Collector
        self.assertTrue(isinstance(self.streams_data_source._collector, PipesCollector))

    async def test_open(self):
        self.assertTrue(all(s._stream_state == StreamState.CLOSED for s in self.streams_data_source._streams.values()))
        with patch.object(StreamDataSource, "subscribe", new=AsyncMock()) as subscribe_stream_mock:
            await self.streams_data_source.open()
            subscribe_stream_mock.assert_called()
            subscribe_stream_mock.assert_awaited()
            self.assertEqual(len(self.streams_data_source._streams), subscribe_stream_mock.await_count)
        self.assertTrue(all(s._stream_state == StreamState.OPENED for s in self.streams_data_source._streams.values()))
        self.assertTrue(all(s._ws_assistant == self.ws_assistant for s in self.streams_data_source._streams.values()))
        self.assertEqual(len(self.streams_data_source._streams), self.ws_assistant.connect_count)

    async def test_open_with_failure(self):
        # Simulate a failure when opening one of the StreamDataSource instances
        list(self.streams_data_source._streams.values())[0]._stream_state = StreamState.SUBSCRIBED

        await self.streams_data_source.open()
        # The failed StreamDataSource instance should be removed from the _streams dict
        self.assertEqual(len(self.channels) * len(self.trading_pairs) - 1, len(self.streams_data_source._streams))
        self.assertTrue(all(s._stream_state == StreamState.OPENED for s in self.streams_data_source._streams.values()))

    async def test_close(self):
        # Assume that all StreamDataSource instances are successfully closed
        await self.streams_data_source.open()
        self.assertTrue(all(s._stream_state == StreamState.OPENED for s in self.streams_data_source._streams.values()))
        self.assertEqual(len(self.streams_data_source._streams), self.ws_assistant.connect_count)
        self.assertEqual(0, self.ws_assistant.disconnect_count)

        with patch.object(StreamDataSource, "unsubscribe", new=AsyncMock()) as unsubscribe_stream_mock:
            await self.streams_data_source.close()
            unsubscribe_stream_mock.assert_called()
            unsubscribe_stream_mock.assert_awaited()
            self.assertEqual(len(self.streams_data_source._streams), unsubscribe_stream_mock.await_count)
        self.assertTrue(all(s._stream_state == StreamState.CLOSED for s in self.streams_data_source._streams.values()))
        self.assertEqual(len(self.streams_data_source._streams), self.ws_assistant.disconnect_count)

    async def test_subscribe(self):
        await self.streams_data_source.open()
        self.assertTrue(all(s._stream_state == StreamState.OPENED for s in self.streams_data_source._streams.values()))

        with patch.object(StreamDataSource, "_send_to_stream", new=AsyncMock()) as send_to_stream_mock:
            await self.streams_data_source.subscribe()
            send_to_stream_mock.assert_called()
            send_to_stream_mock.assert_awaited()
            self.assertEqual(len(self.streams_data_source._streams), send_to_stream_mock.await_count)

        self.assertTrue(
            all(s._stream_state == StreamState.SUBSCRIBED for s in self.streams_data_source._streams.values()))

    async def test_unsubscribe(self):
        # Assume that all StreamDataSource instances are successfully unsubscribed
        for stream in self.streams_data_source._streams.values():
            stream._stream_state = StreamState.UNSUBSCRIBED

        await self.streams_data_source.unsubscribe()
        for stream in self.streams_data_source._streams.values():
            self.assertEqual(StreamState.UNSUBSCRIBED, stream._stream_state)

    @patch.object(PipeBlock, "start_task", new=AsyncMock(return_value="mocked result"))
    @patch.object(StreamDataSource, "start_task", new=AsyncMock(return_value="mocked result"))
    @patch.object(TaskManager, "start_task", new=AsyncMock(return_value="mocked result"))
    async def test_start_stream(self):
        streams_data_source = _MultiStreamDataSource(
            channels=self.channels,
            pairs=self.trading_pairs,
            ws_factory=self.partial_assistant,
            ws_url="ws://localhost:1234",
            pair_to_symbol=self.pair_to_symbol,
            symbol_to_pair=self.symbol_to_pair,
            subscription_builder=self.subscription_builder,
            heartbeat_channel=self.heartbeat_channel,
        )

        # Assume that all tasks are successfully started
        for stream in streams_data_source._streams.values():
            stream._task_state = TaskState.STARTED

        await streams_data_source.start_stream()

        for stream in streams_data_source._streams.values():
            self.assertEqual(TaskState.STARTED, stream._task_state)
        # await streams_data_source.stop_stream()
