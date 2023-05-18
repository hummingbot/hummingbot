import asyncio
import unittest
from collections import defaultdict
from typing import Any, Coroutine
from unittest.mock import AsyncMock, call, patch

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_api_user_stream_data_source import (
    CoinbaseAdvancedTradeAPIUserStreamDataSource,
    CoinbaseAdvancedTradeAuthProtocol,
    CoinbaseAdvancedTradeExchangePairProtocol,
    CoinbaseAdvancedTradeWebAssistantsFactoryProtocol,
    CoinbaseAdvancedTradeWSAssistantProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants import WS_ACTION
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest


class MockWebAssistant(CoinbaseAdvancedTradeWSAssistantProtocol):
    async def connect(self, ws_url: str, ping_timeout: int) -> Coroutine[Any, Any, Coroutine[Any, Any, None]]:
        pass

    async def send(self, request: WSJSONRequest) -> Coroutine[Any, Any, None]:
        pass


class MockExchangePair(CoinbaseAdvancedTradeExchangePairProtocol):
    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        return f"{trading_pair}-symbol"


class MockAuth(CoinbaseAdvancedTradeAuthProtocol):
    pass


class MockWebAssistantsFactory(CoinbaseAdvancedTradeWebAssistantsFactoryProtocol):
    async def get_ws_assistant(self) -> CoinbaseAdvancedTradeWSAssistantProtocol:
        return MockWebAssistant()


class MockDataSource(CoinbaseAdvancedTradeAPIUserStreamDataSource):
    async def _connected_websocket_assistant(self) -> CoinbaseAdvancedTradeWSAssistantProtocol:
        return MockWebAssistant()

    async def _subscribe_channels(self, ws: CoinbaseAdvancedTradeWSAssistantProtocol) -> None:
        pass


class CoinbaseAdvancedTradeAPIUserStreamDataSourceTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self):
        self.auth = MockAuth()
        self.trading_pairs = ["ETH-USD", "BTC-USD"]
        self.connector = MockExchangePair()
        self.api_factory = MockWebAssistantsFactory()
        self.ws_assistant_mock = AsyncMock()

        self.data_source = CoinbaseAdvancedTradeAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory
        )
        self.data_source._manage_queue = AsyncMock()

        self.log_records = []
        self.data_source.logger().setLevel(self.level)
        self.data_source.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def test_init(self):
        self.assertEqual(self.auth, self.data_source._auth)
        self.assertEqual(self.trading_pairs, self.data_source._trading_pairs)
        self.assertEqual(self.connector, self.data_source._connector)
        self.assertEqual(self.api_factory, self.data_source._api_factory)
        self.assertEqual(CONSTANTS.DEFAULT_DOMAIN, self.data_source._domain)

        switch_domain = "us"
        data_source = CoinbaseAdvancedTradeAPIUserStreamDataSource(
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

    def test_init_message_queue(self):
        async def async_test():
            # Creation of a queue with default initialization to an asyncio.Queue
            # This needs to be done within an async context
            self.assertIsInstance(self.data_source._message_queue[CONSTANTS.WS_USER_SUBSCRIPTION_KEYS[0]],
                                  asyncio.Queue)
            self.assertEqual(1, len(self.data_source._message_queue))
            await asyncio.sleep(0)
            await self.data_source.close()
        asyncio.run(async_test())

    def test_async_init(self):
        async def run_test():
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
        asyncio.run(run_test())

    def test_connected_websocket_assistant(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            self.assertIsInstance(ws_assistant, CoinbaseAdvancedTradeWSAssistantProtocol)
            self.assertFalse(CONSTANTS.WS_USER_SUBSCRIPTION_KEYS[0] in self.data_source._message_queue)

            await self.data_source.close()

        asyncio.run(async_test())

    def test_connected_websocket_assistant_connect_call(self):
        async def async_test():
            with patch.object(MockWebAssistant, "connect", new_callable=AsyncMock) as mock_connect:
                await self.data_source._connected_websocket_assistant()
                mock_connect.assert_called_once_with(ws_url=CONSTANTS.WSS_URL.format(domain=self.data_source._domain),
                                                     ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
            await self.data_source.close()

        asyncio.run(async_test())

    def test_subscribe_channels_send_call(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
                await self.data_source._subscribe_channels(ws_assistant)
                self.assertEqual(mock_send.call_count,
                                 len(self.data_source._queue_keys) * len(self.data_source._trading_pairs))
            await self.data_source.close()

        asyncio.run(async_test())

    def test_subscribe_channels(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            await self.data_source._subscribe_channels(ws_assistant)
            await self.data_source.close()

        asyncio.run(async_test())

    def test_subscribe_channels_with_exception_logging(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock, side_effect=Exception) as mock_error:
                with self.assertRaises(Exception):
                    await self.data_source._subscribe_channels(ws_assistant)
                # The exception interrupts the subscription loop, but the exception is logged
                self.assertTrue(
                    self._is_logged("ERROR", "Unexpected error occurred Subscribe-ing to user for ETH-USD..."))
                self.assertEqual(1, mock_error.call_count)
                self.assertNotEqual(len(self.data_source._queue_keys) * len(self.data_source._trading_pairs),
                                    mock_error.call_count)
            await self.data_source.close()

        asyncio.run(async_test())

    def test_unsubscribe_channels_send_call(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
                await self.data_source._unsubscribe_channels(ws_assistant)
                self.assertEqual(mock_send.call_count,
                                 len(self.data_source._queue_keys) * len(self.data_source._trading_pairs))
            await self.data_source.close()

        asyncio.run(async_test())

    def test_unsubscribe_channels_with_exception_logging(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock, side_effect=Exception) as mock_error:
                with self.assertRaises(Exception):
                    await self.data_source._unsubscribe_channels(ws_assistant)
                # The exception interrupts the subscription loop, but the exception is logged
                self.assertTrue(
                    self._is_logged("ERROR", "Unexpected error occurred Unsubscribe-ing to user for ETH-USD..."))
                self.assertEqual(1, mock_error.call_count)
                self.assertNotEqual(len(self.data_source._queue_keys) * len(self.data_source._trading_pairs),
                                    mock_error.call_count)
            await self.data_source.close()

        asyncio.run(async_test())

    def test_subscribe_or_unsubscribe_subscribe(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
                await self.data_source._subscribe_or_unsubscribe(ws_assistant, WS_ACTION.SUBSCRIBE, ["user"],
                                                                 ["ETH-USD"])
                mock_send.assert_called_once()
                self.data_source._manage_queue.assert_called_once()

            await self.data_source.close()

        asyncio.run(async_test())

    def test_payload_format(self):
        async def run_test():
            action = WS_ACTION.SUBSCRIBE
            channels = ["channel1", "channel2"]
            trading_pairs = ["pair1", "pair2"]

            self.data_source._connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="symbol")

            await self.data_source._subscribe_or_unsubscribe(self.ws_assistant_mock, action, channels, trading_pairs)

            expected_payloads = [
                {"type": action.value, "product_ids": ["symbol"], "channel": channel}
                for channel in channels
                for _ in trading_pairs
            ]

            self.ws_assistant_mock.send.assert_has_calls(
                [call(WSJSONRequest(payload=payload)) for payload in expected_payloads],
                any_order=True
            )

            await self.data_source.close()

        asyncio.run(run_test())

    def test_subscribe_or_unsubscribe_with_exception_logging(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock, side_effect=Exception) as mock_error:
                with self.assertRaises(Exception):
                    await self.data_source._subscribe_or_unsubscribe(ws_assistant, WS_ACTION.SUBSCRIBE, ["user"],
                                                                     ["ETH-USD"])
                # The exception interrupts the subscription loop, but the exception is logged
                self.assertTrue(
                    self._is_logged("ERROR", "Unexpected error occurred Subscribe-ing to user for ETH-USD..."))
                self.assertEqual(1, mock_error.call_count)
                self.assertNotEqual(len(self.data_source._queue_keys) * len(self.data_source._trading_pairs),
                                    mock_error.call_count)
            await self.data_source.close()

        asyncio.run(async_test())

    def test_subscribe_or_unsubscribe_unsubscribe(self):
        async def async_test():
            ws_assistant = await self.data_source._connected_websocket_assistant()
            with patch.object(MockWebAssistant, "send", new_callable=AsyncMock) as mock_send:
                await self.data_source._subscribe_or_unsubscribe(ws_assistant, WS_ACTION.UNSUBSCRIBE, ["user"],
                                                                 ["ETH-USD"])
                mock_send.assert_called_once()
                self.data_source._manage_queue.assert_called_once()

            await self.data_source.close()

        asyncio.run(async_test())


if __name__ == '__main__':
    unittest.main()
