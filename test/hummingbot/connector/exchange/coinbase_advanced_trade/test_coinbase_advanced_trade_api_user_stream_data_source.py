import asyncio
import contextlib
import functools
import random
import unittest
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, call, patch

from hummingbot.connector.exchange.coinbase_advanced_trade import coinbase_advanced_trade_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_api_user_stream_data_source import (
    CoinbaseAdvancedTradeAPIUserStreamDataSource,
    CoinbaseAdvancedTradeCumulativeUpdate,
    MultiStreamDataSource,
    coinbase_advanced_trade_subscription_builder,
    message_to_cumulative_update,
    sequence_reader,
    timestamp_and_filter,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.enums import StreamAction, StreamState
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.protocols import WSAssistantPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskState
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.logger import HummingbotLogger


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


class CoinbaseAdvancedTradeAPIUserStreamDataSourceTests(
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

        self.cumulative_update = CoinbaseAdvancedTradeCumulativeUpdate(
            exchange_order_id="123",
            client_order_id="456",
            status="done",
            trading_pair="ETH-USD",
            fill_timestamp_s=123456789,
            average_price=Decimal("123.456"),
            cumulative_base_amount=Decimal("123.456"),
            remainder_base_amount=Decimal("123.456"),
            cumulative_fee=Decimal("123.456"),
        )
        self.data_source = CoinbaseAdvancedTradeAPIUserStreamDataSource(
            channels=self.channels,
            pairs=self.trading_pairs,
            ws_factory=self.partial_assistant,
            ws_url="ws://localhost:1234",
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
        self.assertIsInstance(self.data_source._stream_to_queue, MultiStreamDataSource, )
        self.assertEqual(4, len(self.data_source._stream_to_queue.states))
        self.assertTrue(
            all(s == (StreamState.CLOSED, TaskState.STOPPED) for s in self.data_source._stream_to_queue.states))
        self.assertEqual(0, self.ws_assistant.connect_count)

    async def test_listen_for_user_stream_mocked(self):
        with patch.object(self.data_source, "_stream_to_queue",
                          AsyncMock(spec=MultiStreamDataSource)) as stream_to_queue_mock:
            side_effects = [self.cumulative_update for _ in range(random.randint(5, 10))]
            stream_to_queue_mock.queue.get = AsyncMock(side_effect=side_effects)

            with contextlib.suppress(StopAsyncIteration):
                await self.data_source.listen_for_user_stream(self.output_queue)

        stream_to_queue_mock.start_streams.assert_called_once()
        stream_to_queue_mock.subscribe.assert_called_once()
        # The number of calls to get should be the number of side effects + 1 for the StopAsyncIteration
        self.assertEqual(len(side_effects) + 1, stream_to_queue_mock.queue.get.call_count)
        # The number of calls to put should be the number of side effects
        self.assertEqual(len(side_effects), self.output_queue.qsize())

    async def test_connected_websocket_assistant_connect_call(self):
        with self.assertRaises(NotImplementedError):
            await self.data_source._connected_websocket_assistant()

    async def test_subscribe_channels_send_call(self):
        with self.assertRaises(NotImplementedError):
            await self.data_source._subscribe_channels(self.ws_assistant)


class TestSequenceReader(IsolatedAsyncioWrapperTestCase):

    @patch.object(HummingbotLogger, "debug")
    async def test_sequence_reader_user_channel(self, mock_debug):
        message = {
            "channel": "user",
            "sequence_num": 1
        }
        sequence_num = sequence_reader(message, logger=HummingbotLogger)
        self.assertEqual(sequence_num, 1)
        mock_debug.assert_called_with("Sequence handler user:1:{'channel': 'user', 'sequence_num': 1}")

    @patch.object(HummingbotLogger, "debug")
    async def test_sequence_reader_other_channel(self, mock_debug):
        message = {
            "channel": "other",
            "sequence_num": 2
        }
        sequence_num = sequence_reader(message, logger=HummingbotLogger)
        self.assertEqual(sequence_num, 2)
        mock_debug.assert_has_calls([
            call("Sequence handler other:2"),
            call("{'channel': 'other', 'sequence_num': 2}")
        ])

    async def test_sequence_reader_no_logger(self):
        message = {
            "channel": "user",
            "sequence_num": 1
        }
        sequence_num = sequence_reader(message)
        self.assertEqual(sequence_num, 1)


class TestCoinbaseAdvancedTradeSubscriptionBuilder(IsolatedAsyncioWrapperTestCase):

    async def test_subscription_builder_subscribe(self):
        pair_to_symbol_mock = AsyncMock(return_value="ETH-USD")
        result = await coinbase_advanced_trade_subscription_builder(
            action=StreamAction.SUBSCRIBE,
            channel="level2",
            pair="ETH-USD",
            pair_to_symbol=pair_to_symbol_mock
        )
        self.assertEqual(result, {
            "type": "subscribe",
            "product_ids": ["ETH-USD"],
            "channel": "level2"
        })
        pair_to_symbol_mock.assert_awaited_with("ETH-USD")

    async def test_subscription_builder_unsubscribe(self):
        pair_to_symbol_mock = AsyncMock(return_value="ETH-USD")
        result = await coinbase_advanced_trade_subscription_builder(
            action=StreamAction.UNSUBSCRIBE,
            channel="level2",
            pair="ETH-USD",
            pair_to_symbol=pair_to_symbol_mock
        )
        self.assertEqual(result, {
            "type": "unsubscribe",
            "product_ids": ["ETH-USD"],
            "channel": "level2"
        })
        pair_to_symbol_mock.assert_awaited_with("ETH-USD")

    async def test_subscription_builder_invalid_action(self):
        pair_to_symbol_mock = AsyncMock()
        with self.assertRaises(ValueError):
            await coinbase_advanced_trade_subscription_builder(
                action="invalid_action",
                channel="level2",
                pair="ETH-USD",
                pair_to_symbol=pair_to_symbol_mock
            )
        pair_to_symbol_mock.assert_not_awaited()


class TestTimestampAndFilter(unittest.TestCase):

    def test_filter_user_channel_with_str_timestamp(self):
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade'
                   '.coinbase_advanced_trade_api_user_stream_data_source.get_timestamp_from_exchange_time',
                   return_value=1678900000) as mock_get_timestamp:
            event_message: Dict[str, Any] = {
                "channel": "user",
                "timestamp": "2023-02-09T20:33:57.609931463Z",
                "sequence_num": 0,
                "events": []
            }
            result: Generator[Dict[str, Any], None, None] = timestamp_and_filter(event_message)
            expected_output = {
                "channel": "user",
                "timestamp": 1678900000,
                "sequence_num": 0,
                "events": []
            }
            self.assertEqual(next(result), expected_output)
            mock_get_timestamp.assert_called_with("2023-02-09T20:33:57.609931463Z", "s")

    def test_filter_non_user_channel(self):
        event_message: Dict[str, Any] = {
            "channel": "not_user",
            "timestamp": "2023-02-09T20:33:57.609931463Z",
            "sequence_num": 0,
            "events": []
        }
        result: Generator[Dict[str, Any], None, None] = timestamp_and_filter(event_message)
        with self.assertRaises(StopIteration):
            next(result)


class TestMessageToCumulativeUpdate(IsolatedAsyncioWrapperTestCase):

    async def test_valid_message(self):
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade'
                   '.coinbase_advanced_trade_api_user_stream_data_source.get_timestamp_from_exchange_time',
                   return_value=1678900000):
            symbol_to_pair = AsyncMock(return_value="BTC-USD")
            event_message: Dict[str, Any] = {
                "channel": "user",
                "timestamp": "2023-02-09T20:33:57.609931463Z",
                "sequence_num": 0,
                "events": [
                    {
                        "type": "snapshot",
                        "orders": [
                            {
                                "order_id": "XXX",
                                "client_order_id": "YYY",
                                "cumulative_quantity": "0",
                                "leaves_quantity": "0.000994",
                                "avg_price": "0",
                                "total_fees": "0",
                                "status": "OPEN",
                                "product_id": "BTC-USD",
                                "creation_time": "2022-12-07T19:42:18.719312Z",
                                "order_side": "BUY",
                                "order_type": "Limit"
                            }
                        ]
                    }
                ]
            }
            async for cumulative_order in message_to_cumulative_update(event_message, symbol_to_pair=symbol_to_pair):
                self.assertIsInstance(cumulative_order, CoinbaseAdvancedTradeCumulativeUpdate)
                self.assertEqual(cumulative_order.exchange_order_id, "XXX")
                self.assertEqual(cumulative_order.client_order_id, "YYY")
                self.assertEqual(cumulative_order.status, "OPEN")
                self.assertEqual(cumulative_order.trading_pair, "BTC-USD")
                self.assertEqual(cumulative_order.fill_timestamp_s, 1678900000)
                self.assertEqual(cumulative_order.average_price, Decimal("0"))
                self.assertEqual(cumulative_order.cumulative_base_amount, Decimal("0"))
                self.assertEqual(cumulative_order.remainder_base_amount, Decimal("0.000994"))
                self.assertEqual(cumulative_order.cumulative_fee, Decimal("0"))

    async def test_invalid_message(self):
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade'
                   '.coinbase_advanced_trade_api_user_stream_data_source.get_timestamp_from_exchange_time',
                   return_value=1678900000):
            symbol_to_pair = AsyncMock(return_value="BTC-USD")
            event_message: Dict[str, Any] = {
                "channel": "user",
                "timestamp": "2023-02-09T20:33:57.609931463Z",
                "sequence_num": 0,
                "events": [
                    {
                        "type": "snapshot",
                        "orders": [
                            {
                                "order_id": "XXX",
                                "client_order_id": "YYY",
                                "cumulative_quantity": "invalid",
                                "leaves_quantity": "0.000994",
                                "avg_price": "0",
                                "total_fees": "0",
                                "status": "OPEN",
                                "product_id": "BTC-USD",
                                "creation_time": "2022-12-07T19:42:18.719312Z",
                                "order_side": "BUY",
                                "order_type": "Limit"
                            }
                        ]
                    }
                ]
            }
            with self.assertRaises(Exception):
                async for _ in message_to_cumulative_update(event_message, symbol_to_pair=symbol_to_pair):
                    pass


if __name__ == '__main__':
    unittest.main()
