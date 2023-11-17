import asyncio
import functools
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.enums import StreamAction, StreamState
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.protocols import WSAssistantPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.stream_data_source import StreamDataSource
from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskManager, TaskState
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSRequest, WSResponse


class MockWebAssistant(WSAssistantPtl):
    def __init__(self):
        self.send_args = None
        self.connect_args = None
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

    async def disconnect(self) -> None:
        self.disconnect_called = True

    async def receive(self) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        self.receive_called = True

    async def send(self, request: WSRequest) -> None:
        self.send_called = True
        self.send_args = request


class MockExchangePair:
    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        return f"{trading_pair}-symbol"


class TestStreamDataSource(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    quote_asset = None
    base_asset = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()
        self.channel = "test_channel"
        self.base_asset = "COINALPHA"
        self.quote_asset = "HBOT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.trading_pairs = ["COINALPHA-HBOT", "COINALPHA-TOBH"]
        self.ex_trading_pair = f"{self.base_asset}-{self.quote_asset}"

        self.get_ws_assistant_called = False
        self.get_ws_assistant_args = None
        self.iter_messages_called = False
        self.iter_messages_count = None
        self.ws_assistant = MockWebAssistant()
        self.ws_assistant.iter_messages = self.iter_messages
        self.partial_assistant = functools.partial(self.get_ws_assistant, self.ws_assistant)
        self.heartbeat_channel = "heartbeats"
        self.stream_data_source = StreamDataSource(
            channel=self.channel,
            pair=self.trading_pair,
            ws_factory=self.partial_assistant,
            ws_url="wss://test_url",
            pair_to_symbol=self.pair_to_symbol,
            subscription_builder=self.subscription_builder,
            heartbeat_channel=self.heartbeat_channel,
        )
        self.set_loggers([self.stream_data_source.logger()])

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.symbol = await self.pair_to_symbol(f"{self.base_asset}-{self.quote_asset}")
        # Reset the mock
        self.pair_to_symbol_called = False
        self.pair_to_symbol_args = None

    async def asyncTearDown(self) -> None:
        await self.stream_data_source.close_connection()
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

    async def iter_messages(self) -> AsyncGenerator[WSResponse | None, None]:
        self.iter_messages_called = True
        self.iter_messages_count += 1
        for m in ("message0", "message1", "message2"):
            yield WSResponse(data={'message': m})
        return

    async def test_initialization_sets_correct_attributes(self) -> None:
        self.assertEqual(self.channel, self.stream_data_source._channel, )
        self.assertEqual(self.trading_pair, self.stream_data_source._pair, )
        self.assertEqual(self.partial_assistant,
                         self.stream_data_source._ws_factory)
        self.assertEqual(self.subscription_builder,
                         self.stream_data_source._subscription_builder.func)
        self.assertEqual(None, self.stream_data_source._ws_assistant, )
        self.assertEqual(self.heartbeat_channel, self.stream_data_source._heartbeat_channel, )
        self.assertIsInstance(self.stream_data_source._subscription_lock, asyncio.Lock, )
        self.assertEqual(0.0, self.stream_data_source._last_recv_time_s, )
        self.assertEqual(StreamState.CLOSED, self.stream_data_source._stream_state, )
        self.assertEqual(TaskState.STOPPED, self.stream_data_source._task_state, )

        # Properties
        self.assertEqual(self.channel, self.stream_data_source.channel, )
        self.assertEqual(self.trading_pair, self.stream_data_source.pair, )
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream_data_source.state, )

    async def test_ws_factory_called(self):
        await self.stream_data_source._ws_factory()
        self.assertTrue(self.get_ws_assistant_called)

    async def test__subscription_builder_after_init_subscribe(self):
        payload = await self.stream_data_source._subscription_builder(
            action=StreamAction.SUBSCRIBE,
            channel=self.channel,
        )
        self.assertTrue(self.pair_to_symbol_called)
        self.assertEqual("subscribe", payload["type"])
        self.assertEqual([self.symbol], payload["product_ids"])
        self.assertEqual(self.channel, payload["channel"])

    async def test__subscription_builder_after_init_unsubscribe(self):
        payload = await self.stream_data_source._subscription_builder(
            action=StreamAction.UNSUBSCRIBE,
            channel=self.channel,
        )
        self.assertTrue(self.pair_to_symbol_called)
        self.assertEqual("unsubscribe", payload["type"])
        self.assertEqual([self.symbol], payload["product_ids"])
        self.assertEqual(self.channel, payload["channel"])

    async def test_open(self) -> None:
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream_data_source.state, )
        self.assertFalse(self.get_ws_assistant_called)
        self.assertFalse(self.pair_to_symbol_called)
        self.assertEqual(None, self.stream_data_source._ws_assistant)

        await self.stream_data_source.open_connection()

        self.assertEqual((StreamState.OPENED, TaskState.STOPPED), self.stream_data_source.state, )
        self.assertTrue(self.get_ws_assistant_called)
        self.assertTrue(self.pair_to_symbol_called)
        self.assertTrue(self.stream_data_source._ws_assistant.connect_called)
        self.assertEqual({
            'ws_url': 'wss://test_url',
            'ping_timeout': 30.0,
            'message_timeout': None,
            'ws_headers': None
        },
            self.stream_data_source._ws_assistant.connect_args)

    async def test_subscribe(self) -> None:
        await self.stream_data_source.open_connection()
        self.assertEqual((StreamState.OPENED, TaskState.STOPPED), self.stream_data_source.state, )

        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            await self.stream_data_source.subscribe()
            mock_subscribe.assert_called_once()
            mock_subscribe.assert_awaited_once()

        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STOPPED), self.stream_data_source.state, )

    async def test_subscribe_when_already_subscribed(self) -> None:
        self.stream_data_source._stream_state = StreamState.SUBSCRIBED

        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            await self.stream_data_source.subscribe(set_state=False)
            mock_subscribe.assert_not_called()
            mock_subscribe.assert_not_awaited()

        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STOPPED), self.stream_data_source.state, )
        # self.assertTrue(
        #     self.is_logged("WARNING", f"Attempted to subscribe to {self.channel}/{self.trading_pair} "
        #                               f"stream while already subscribed."))

    async def test_subscribe_without_states_mocked(self) -> None:
        await self.stream_data_source.open_connection()
        self.assertEqual((StreamState.OPENED, TaskState.STOPPED), self.stream_data_source.state)

        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            await self.stream_data_source.subscribe(set_state=False)
            mock_subscribe.assert_called_once()
            mock_subscribe.assert_awaited_once()

        # The intent is to subscribe to a secondary channel, so the state should remain OPENED
        self.assertEqual((StreamState.OPENED, TaskState.STOPPED), self.stream_data_source.state)

    async def test__send_to_stream(self) -> None:
        await self.stream_data_source.open_connection()
        self.assertEqual((StreamState.OPENED, TaskState.STOPPED), self.stream_data_source.state, )
        builder = functools.partial(self.stream_data_source._subscription_builder,
                                    action=StreamAction.SUBSCRIBE,
                                    channel=self.channel, )
        await self.stream_data_source._send_to_stream(subscription_builder=builder)

        self.assertTrue(self.stream_data_source._ws_assistant.send_called)
        self.assertEqual(WSJSONRequest(payload={
            "type": "subscribe",
            "product_ids": [self.symbol],
            "channel": self.channel,
        }, is_auth_required=True),
            self.stream_data_source._ws_assistant.send_args)
        self.assertEqual((StreamState.OPENED, TaskState.STOPPED), self.stream_data_source.state)

    async def test_unsubscribe_mocked(self) -> None:
        await self.stream_data_source.open_connection()
        await self.stream_data_source.subscribe()
        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STOPPED), self.stream_data_source.state, )

        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            await self.stream_data_source.unsubscribe()
            mock_subscribe.assert_called_once()
            mock_subscribe.assert_awaited_once()

    async def test_unsubscribe(self) -> None:
        await self.stream_data_source.open_connection()
        await self.stream_data_source.subscribe()
        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STOPPED), self.stream_data_source.state, )

        await self.stream_data_source.unsubscribe()

        self.assertTrue(self.stream_data_source._ws_assistant.send_called)
        self.assertEqual(WSJSONRequest(payload={
            "type": "unsubscribe",
            "product_ids": [self.symbol],
            "channel": self.channel,
        }, is_auth_required=True),
            self.stream_data_source._ws_assistant.send_args)
        self.assertEqual((StreamState.UNSUBSCRIBED, TaskState.STOPPED), self.stream_data_source.state, )

    async def test_unsubscribe_in_correct_state(self) -> None:
        self.stream_data_source._stream_state = StreamState.SUBSCRIBED

        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            await self.stream_data_source.unsubscribe()
            mock_subscribe.assert_called_once()
            mock_subscribe.assert_awaited_once()
            self.assertEqual(StreamState.UNSUBSCRIBED, self.stream_data_source._stream_state, )

    async def test_unsubscribe_in_incorrect_state(self) -> None:
        self.stream_data_source._stream_state = StreamState.OPENED

        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            await self.stream_data_source.unsubscribe()
            mock_subscribe.assert_not_called()
            mock_subscribe.assert_not_awaited()
            self.assertEqual(StreamState.OPENED, self.stream_data_source._stream_state, )
            # The internal _symbol was not initialized, so it is not yet the same as self.symbol
            # self.assertTrue(
            #     self.is_logged(
            #         "WARNING",
            #         f"Attempted to unsubscribe from {self.channel}/{self.trading_pair} stream while not subscribed.",
            #     )
            # )

        self.stream_data_source._stream_state = StreamState.CLOSED
        with patch.object(StreamDataSource, "_send_to_stream", new_callable=AsyncMock) as mock_subscribe:
            mock_subscribe.assert_not_called()
            mock_subscribe.assert_not_awaited()
            self.assertEqual(StreamState.CLOSED, self.stream_data_source._stream_state, )
            # The internal _symbol was not initialized, so it is not yet the same as self.symbol
            # self.assertTrue(
            #     self.is_logged(
            #         "WARNING",
            #         f"Attempted to unsubscribe from {self.channel}/{self.trading_pair} stream while not subscribed.",
            #     )
            # )

    async def test_close_with_mock(self) -> None:
        await self.stream_data_source.open_connection()
        await self.stream_data_source.subscribe()
        self.assertEqual(StreamState.SUBSCRIBED, self.stream_data_source._stream_state, )
        self.assertEqual(self.ws_assistant, self.stream_data_source._ws_assistant, )

        with patch.object(self.ws_assistant, "disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch.object(StreamDataSource, "unsubscribe", new_callable=AsyncMock) as mock_unsubscribe:
                await self.stream_data_source.close_connection()
                mock_unsubscribe.assert_called_once()
                mock_unsubscribe.assert_awaited_once()
                mock_disconnect.assert_called_once()
                mock_disconnect.assert_awaited_once()
                self.assertEqual(StreamState.CLOSED, self.stream_data_source._stream_state, )

    async def test_close_with_mock_exception(self) -> None:
        await self.stream_data_source.open_connection()
        await self.stream_data_source.subscribe()
        self.assertEqual(StreamState.SUBSCRIBED, self.stream_data_source._stream_state, )
        self.assertEqual(self.ws_assistant, self.stream_data_source._ws_assistant, )

        with patch.object(self.ws_assistant, "disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch.object(StreamDataSource, "unsubscribe", new_callable=AsyncMock) as mock_unsubscribe:
                mock_unsubscribe.side_effect = Exception("Test")
                await self.stream_data_source.close_connection()
                mock_unsubscribe.assert_called_once()
                mock_unsubscribe.assert_awaited_once()
                mock_disconnect.assert_called_once()
                mock_disconnect.assert_awaited_once()
                self.assertTrue(
                    self.is_logged(
                        "ERROR",
                        "Failed to unsubscribe from channels: Test")
                )
                self.assertEqual(StreamState.CLOSED, self.stream_data_source._stream_state, )

    async def test_close(self) -> None:
        await self.stream_data_source.open_connection()
        await self.stream_data_source.subscribe()
        self.assertEqual(StreamState.SUBSCRIBED, self.stream_data_source._stream_state, )
        self.assertEqual(self.ws_assistant, self.stream_data_source._ws_assistant, )

        await self.stream_data_source.close_connection()

        # Attempt to unsubscribe: note that after close the internal _ws_assistant is None
        self.assertEqual(WSJSONRequest(payload={
            "type": "unsubscribe",
            "product_ids": [self.symbol],
            "channel": self.channel,
        }, is_auth_required=True),
            self.ws_assistant.send_args)
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Unsubscribed from {self.channel} for {self.trading_pair}.")
        )
        self.assertEqual(StreamState.CLOSED, self.stream_data_source._stream_state, )

    async def test_start_mocked(self) -> None:
        with patch.object(StreamDataSource, "start_task", new_callable=MagicMock) as mock_task:
            self.assertFalse(self.stream_data_source.is_running())

            await self.stream_data_source.start_stream()

            # Note that we check that the TaskManager is running before setting the state to STARTED
            mock_task.assert_called_once()
            # is_running did not change since it is not mocked (default value is false ... of course)
            self.assertFalse(self.stream_data_source.is_running())
            self.assertEqual(TaskState.STOPPED, self.stream_data_source._task_state, )

        with patch.object(TaskManager, "is_running", new_callable=MagicMock(return_value=True)):
            with patch.object(StreamDataSource, "start_task", new_callable=MagicMock) as mock_task:
                await self.stream_data_source.start_stream()
                # With a mocked is_running the state changes to STARTED
                mock_task.assert_called_once()
                # start_all_tasks is mocked
                self.assertEqual(TaskState.STOPPED, self.stream_data_source._task_state, )

    async def test_start_task(self) -> None:
        self.assertFalse(self.stream_data_source.is_running())
        self.assertEqual(TaskState.STOPPED, self.stream_data_source._task_state, )
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream_data_source.state, )

        self.stream_data_source.start_task()

        self.assertTrue(self.stream_data_source.is_running())
        self.assertEqual(TaskState.STARTED, self.stream_data_source._task_state, )
        # Auto-reconnecting Stream will call open_connection
        self.assertEqual(TaskState.STARTED, self.stream_data_source.state[1], )

        # Cleanup: stop the TaskManager, clear the wait for the assistant
        if self.stream_data_source.is_running():
            await self.stream_data_source.stop_task()
            self.stream_data_source._ws_assistant_ready.clear()

    async def test_stop_mocked(self) -> None:
        with patch.object(TaskManager, "is_running", new_callable=MagicMock(return_value=True)):
            with patch.object(StreamDataSource, "stop_task", new_callable=AsyncMock) as mock_task:
                self.assertEqual(StreamState.CLOSED, self.stream_data_source._stream_state)
                self.stream_data_source._task_state = TaskState.STARTED

                await self.stream_data_source.stop_stream()

                # Note that we check that the TaskManager is running before setting the state to STOPPED
                mock_task.assert_called_once()
                mock_task.assert_awaited_once()
                self.assertEqual(TaskState.STARTED, self.stream_data_source._task_state, )

        with patch.object(TaskManager, "is_running", new_callable=MagicMock(return_value=False)):
            with patch.object(StreamDataSource, "stop_task", new_callable=AsyncMock) as mock_task:
                self.stream_data_source._task_state = TaskState.STOPPED

                await self.stream_data_source.stop_stream()

                mock_task.assert_called_once()
                mock_task.assert_awaited_once()
                self.assertEqual(TaskState.STOPPED, self.stream_data_source._task_state, )

    # TODO: Fix this test. It hangs forever
    async def _test_stop(self) -> None:
        await self.stream_data_source.start_stream()
        self.assertTrue(self.stream_data_source.is_running())
        self.assertTrue(self.ws_assistant.send_called)
        self.assertEqual(TaskState.STARTED, self.stream_data_source._task_state, )
        self.assertEqual((StreamState.OPENED, TaskState.STARTED), self.stream_data_source.state, )

        await self.stream_data_source.stop_stream()

        # self.assertFalse(self.stream_data_source.is_running())
        self.assertEqual(TaskState.STOPPED, self.stream_data_source._task_state, )
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream_data_source.state, )

    async def test_subscribe_raises_exception(self):
        self.stream_data_source._stream_state = StreamState.OPENED
        with patch.object(StreamDataSource, "_send_to_stream", side_effect=asyncio.exceptions.TimeoutError):
            with self.assertRaises(asyncio.exceptions.TimeoutError):
                await self.stream_data_source.subscribe()

    async def test_unsubscribe_raises_exception(self):
        self.stream_data_source._stream_state = StreamState.SUBSCRIBED
        with patch.object(StreamDataSource, "_send_to_stream", side_effect=asyncio.exceptions.TimeoutError):
            with self.assertRaises(asyncio.exceptions.TimeoutError):
                await self.stream_data_source.unsubscribe()

    async def test_start_raises_exception(self):
        with patch.object(TaskManager, "start_task", side_effect=asyncio.exceptions.TimeoutError):
            with self.assertRaises(asyncio.exceptions.TimeoutError):
                await self.stream_data_source.start_stream()

    async def test_stop_raises_exception(self):
        with patch.object(TaskManager, "stop_task", side_effect=asyncio.exceptions.TimeoutError):
            with self.assertRaises(asyncio.exceptions.TimeoutError):
                await self.stream_data_source.stop_stream()
