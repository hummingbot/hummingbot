import asyncio
import unittest
from collections import defaultdict
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mxin import TestLoggerMixin
from typing import Any, Awaitable, Coroutine
from unittest.mock import AsyncMock, MagicMock, call, patch

from hummingbot.connector.exchange.coinbase_advanced_trade_v2 import coinbase_advanced_trade_v2_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_api_user_stream_data_source import (
    CoinbaseAdvancedTradeV2APIUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest


class MockWebAssistant:
    async def connect(self, ws_url: str, ping_timeout: int) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        pass

    async def disconnect(self) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        pass

    async def send(self, request: WSJSONRequest) -> Coroutine[Any, Any, None]:
        pass


class MockExchangePair:
    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        return f"{trading_pair}-symbol"


class MockWebAssistantsFactory:
    async def get_ws_assistant(self):
        return MockWebAssistant()


class MockDataSource(CoinbaseAdvancedTradeV2APIUserStreamDataSource):
    async def _connected_websocket_assistant(self):
        return MockWebAssistant()

    async def _subscribe_channels(self, ws) -> None:
        pass


class CoinbaseAdvancedTradeV2APIUserStreamDataSourceTests(
    IsolatedAsyncioWrapperTestCase,
    TestLoggerMixin,
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
        self.trading_pairs = ["ETH-USD", "BTC-USD"]
        self.connector = MockExchangePair()
        self.api_factory = MockWebAssistantsFactory()
        self.ws_assistant_mock = AsyncMock()

        self.data_source = CoinbaseAdvancedTradeV2APIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory
        )
        self.set_loggers([self.data_source.logger()])

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.resume_test_event = asyncio.Event()

    async def asyncTearDown(self) -> None:
        await self.data_source.close()
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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.local_event_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_init(self):
        self.assertEqual(self.trading_pairs, self.data_source._trading_pairs)
        self.assertEqual(self.connector, self.data_source._connector)
        self.assertEqual(self.api_factory, self.data_source._api_factory)
        self.assertEqual(CONSTANTS.DEFAULT_DOMAIN, self.data_source._domain)

        switch_domain = "us"
        data_source = CoinbaseAdvancedTradeV2APIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
            domain=switch_domain
        )
        self.assertEqual(switch_domain, data_source._domain)

    def test_init_queue_keys(self):
        # Verifying the class initialization of the keys
        self.assertIsInstance(self.data_source._queue_keys, tuple)

        # Verifying the class initialization of the keys
        self.assertTrue(all(k in self.data_source._queue_keys for k in CONSTANTS.WS_USER_SUBSCRIPTION_KEYS))
        self.assertEqual(len(CONSTANTS.WS_USER_SUBSCRIPTION_KEYS), len(self.data_source._queue_keys))

        # Verifying the initialization of the empty message queues
        self.assertIsInstance(self.data_source._message_queue, defaultdict)
        self.assertEqual(0, len(self.data_source._message_queue))

    async def test_init_message_queue(self):
        # Creation of a queue with default initialization to an asyncio.Queue
        # This needs to be done within an async context
        self.assertIsInstance(self.data_source._message_queue[CONSTANTS.WS_USER_SUBSCRIPTION_KEYS[0]],
                              asyncio.Queue)
        self.assertEqual(1, len(self.data_source._message_queue))
        await asyncio.sleep(0)
        await self.data_source.close()

    async def test_async_init(self):
        with patch.object(self.data_source, "_preprocess_messages", new_callable=AsyncMock) as mock_preprocess:
            # Call _async_init and check that the async attributes are initialized
            self.data_source._async_init()
            self.assertIsInstance(self.data_source._message_queue_lock, asyncio.Lock)
            self.assertIsInstance(self.data_source._subscription_lock, asyncio.Lock)
            self.assertIsInstance(self.data_source._message_queue_task, asyncio.Task)
            mock_preprocess.assert_called_once()

            # Save references to the async attributes
            message_queue_lock = self.data_source._message_queue_lock
            subscription_lock = self.data_source._subscription_lock
            message_queue_task = self.data_source._message_queue_task

            # Call _async_init again and check that the async attributes are not re-initialized
            self.data_source._async_init()
            self.assertIs(self.data_source._message_queue_lock, message_queue_lock)
            self.assertIs(self.data_source._subscription_lock, subscription_lock)
            self.assertIs(self.data_source._message_queue_task, message_queue_task)
            mock_preprocess.assert_called_once()  # It should still have been called only once

    async def test_connected_websocket_assistant(self):
        await self.data_source._connected_websocket_assistant()
        self.assertFalse(CONSTANTS.WS_USER_SUBSCRIPTION_KEYS[0] in self.data_source._message_queue)

        await self.data_source.close()

    async def test_connected_websocket_assistant_connect_call(self):
        with patch.object(MockWebAssistant, "connect", new_callable=AsyncMock) as mock_connect:
            await self.data_source._connected_websocket_assistant()
            mock_connect.assert_called_once_with(ws_url=CONSTANTS.WSS_URL.format(domain=self.data_source._domain),
                                                 ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        await self.data_source.close()

    async def test_subscribe_channels_send_call(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
            await self.data_source._subscribe_channels(ws_assistant)
            self.assertEqual(mock_send.call_count,
                             len(self.data_source._queue_keys) * len(self.data_source._trading_pairs))
        await self.data_source.close()

    async def test_subscribe_channels(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        await self.data_source._subscribe_channels(ws_assistant)
        await self.data_source.close()

    async def test_unsubscribe_channels_with_exception_logging(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        with patch.object(MockWebAssistant, "send", new_callable=AsyncMock, side_effect=Exception) as mock_error:
            with self.assertRaises(Exception):
                await self.data_source._unsubscribe_channels(ws_assistant)
            # The exception interrupts the subscription loop, but the exception is logged
            self.assertTrue(
                self.is_partially_logged("ERROR", "Unexpected error occurred Unsubscribe-ing to user for ETH-USD..."))
            self.assertEqual(1, mock_error.call_count)
            self.assertNotEqual(len(self.data_source._queue_keys) * len(self.data_source._trading_pairs),
                                mock_error.call_count)
        await self.data_source.close()

    async def test_subscribe_or_unsubscribe_subscribe(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
            await self.data_source._subscribe_or_unsubscribe(ws_assistant, "subscribe", ["user"],
                                                             ["ETH-USD"])
            mock_send.assert_called_once()
            self.data_source._manage_queue.assert_called_once()

        await self.data_source.close()

    async def test_payload_format(self):
        action = "subscribe"
        channels = ["channel1", "channel2"]
        trading_pairs = ["pair1", "pair2"]

        self.data_source._connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="symbol")

        await self.data_source._subscribe_or_unsubscribe(self.ws_assistant_mock, action, channels, trading_pairs)

        expected_payloads = [
            {"type": action, "product_ids": ["symbol"], "channel": channel}
            for channel in channels
            for _ in trading_pairs
        ]

        self.ws_assistant_mock.send.assert_has_calls(
            [call(WSJSONRequest(payload=payload)) for payload in expected_payloads],
            any_order=True
        )

        await self.data_source.close()

    async def test_subscribe_or_unsubscribe_with_exception_logging(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        with patch.object(MockWebAssistant, "disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock, side_effect=Exception) as mock_error:
                with self.assertRaises(Exception):
                    await self.data_source._subscribe_or_unsubscribe(ws_assistant, "subscribe", ["user"],
                                                                     ["ETH-USD"])
                # The exception interrupts the subscription loop, but the exception is logged
            mock_disconnect.assert_called_once()
            self.assertTrue(
                self.is_partially_logged("ERROR", "Unexpected error occurred Subscribe-ing to user for ETH-USD..."))
            self.assertEqual(1, mock_error.call_count)
            self.assertNotEqual(len(self.data_source._queue_keys) * len(self.data_source._trading_pairs),
                                mock_error.call_count)
        await self.data_source.close()

    async def test_subscribe_or_unsubscribe_with_cancel_logging(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        with patch.object(MockWebAssistant, "disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock,
                              side_effect=asyncio.CancelledError) as mock_error:
                with self.assertRaises(asyncio.CancelledError):
                    await self.data_source._subscribe_or_unsubscribe(ws_assistant, "subscribe", ["user"],
                                                                     ["ETH-USD"])
            # The cancelled error causes a ws_assistant call to disconnect()
            mock_disconnect.assert_called_once()
            self.assertTrue(
                self.is_partially_logged("ERROR", "Unexpected error occurred Subscribe-ing to user for ETH-USD..."))
            self.assertEqual(1, mock_error.call_count)
            self.assertNotEqual(len(self.data_source._queue_keys) * len(self.data_source._trading_pairs),
                                mock_error.call_count)
        await self.data_source.close()

    async def test_subscribe_or_unsubscribe_unsubscribe(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
            await self.data_source._subscribe_or_unsubscribe(ws_assistant, "unsubscribe", ["user"],
                                                             ["ETH-USD"])
            mock_send.assert_called_once()
            self.data_source._manage_queue.assert_called_once()

        await self.data_source.close()

    async def test_subscribe_or_unsubscribe_unsubscribe_empty_channels(self):
        ws_assistant = await self.data_source._connected_websocket_assistant()
        # This is needed, with an exception, the tasks of the DS prevent the test to finish
        try:
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
                await self.data_source._subscribe_or_unsubscribe(ws_assistant, "unsubscribe", [],
                                                                 ["ETH-USD"])
                mock_send.assert_not_called()
                self.data_source._manage_queue.assert_not_called()
        except Exception:
            await self.data_source.close()
            self.fail("Should not have thrown an exc")

        await self.data_source.close()

    async def test_manage_queue_unsubscribe(self):
        self.data_source._message_queue = {"channel_symbol": asyncio.Queue()}
        await self.data_source._message_queue["channel_symbol"].put(("test", "test"))
        self.data_source._message_queue_task = asyncio.create_task(asyncio.sleep(1))  # a dummy task
        await self.data_source._manage_queue("channel_symbol", "unsubscribe")
        self.assertTrue(self.data_source._message_queue_task.done())
        self.assertFalse("channel_symbol" in self.data_source._message_queue)

    async def test_manage_queue_subscribe(self):
        self.data_source._preprocess_messages = AsyncMock()
        await self.data_source._manage_queue("channel_symbol", "subscribe")
        self.assertIsNotNone(self.data_source._message_queue_task)
        await self.data_source.close()

    async def test_manage_queue_invalid_action(self):
        await self.data_source._manage_queue("channel_symbol", "invalid_action")
        self.assertTrue(
            self.is_partially_logged("ERROR", "Unsupported action "))
        self.assertIsNone(self.data_source._message_queue_task)


if __name__ == '__main__':
    unittest.main()
