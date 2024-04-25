import asyncio
import decimal
import functools
import unittest
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade import coinbase_advanced_trade_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_api_user_stream_data_source import (
    CoinbaseAdvancedTradeAPIUserStreamDataSource,
    CoinbaseAdvancedTradeCumulativeUpdate,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_auth import CoinbaseAdvancedTradeAuth
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_exchange import (
    CoinbaseAdvancedTradeExchange,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class MockWebAssistant:
    def __init__(self):
        self.iter_messages_called = None
        self.iter_messages_count = 0
        self.last_recv_time = None
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

    async def iter_messages(self, *, data) -> AsyncGenerator[WSResponse | None, None]:
        """Will yield None and stop if `WSDelegate.disconnect()` is called while waiting for a response."""
        self.iter_messages_called = True
        self.iter_messages_count += 1
        yield data


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
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.channel = "user"
        self.trading_pairs = ["ETH-USD", "BTC-USD"]
        self.output_queue = asyncio.Queue()
        self.listening_task: asyncio.Task | None = None

        self.cumulative_update = CoinbaseAdvancedTradeCumulativeUpdate(
            client_order_id='YYY',
            exchange_order_id='XXX',
            status='OPEN',
            trading_pair='BTC-USD',
            fill_timestamp_s=1678900000,
            average_price=Decimal('0'),
            cumulative_base_amount=Decimal('0'),
            remainder_base_amount=Decimal('0.000994'),
            cumulative_fee=Decimal('0'),
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp_s=1678900000,
            is_taker=False)

        self.event_message = {
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
                        },
                    ]
                }
            ]
        }

        self.api_factory = Mock(spec=WebAssistantsFactory)
        self.data_source = CoinbaseAdvancedTradeAPIUserStreamDataSource(
            auth=Mock(spec=CoinbaseAdvancedTradeAuth),
            trading_pairs=self.trading_pairs,
            api_factory=self.api_factory,
            connector=Mock(spec=CoinbaseAdvancedTradeExchange),
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
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    async def get_ws_assistant(self, *args, **kwargs):
        self.get_ws_assistant_called = True
        self.get_ws_assistant_args = [args, kwargs]
        self.get_ws_assistant_count += 1
        return MockWebAssistant()

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

    async def test_connected_websocket_assistant_without_pair(self):
        self.api_factory.get_ws_assistant = AsyncMock(side_effect=[AsyncMock(), AsyncMock()])

        await self.data_source._connected_websocket_assistant()

        self.api_factory.get_ws_assistant.call_count = 2
        self.data_source._ws_assistant.connect.assert_called_once()
        self.data_source._ws_assistant.connect.assert_called_with(
            ws_url=CONSTANTS.WSS_URL.format(domain=self.domain),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )

    async def test_last_recv_time(self):
        self.data_source._ws_assistant = MagicMock()
        self.data_source._ws_assistant.last_recv_time = 1234567890.0

        result = self.data_source.last_recv_time

        self.assertEqual(1234567890.0, result, )

    async def test_process_websocket_messages(self):
        queue = asyncio.Queue()
        data = {
            "channel": "user",
            "timestamp": "2023-02-09T20:33:57.609931463Z",
            "sequence_num": 0,
            "events": [
                {
                    "type": "snapshot",
                    "orders": [
                        {
                            "order_id": "order1",
                        },
                        {
                            "order_id": "order2",
                        }
                    ]
                },
                {
                    "type": "update",
                    "orders": [
                        {
                            "order_id": "order3",
                        },
                        {
                            "order_id": "order4",
                        }
                    ]
                }
            ]
        }
        response = Mock(spec=WSResponse)
        response.data = data
        # Provide the data that the assistant should iterate upon
        ws_assistant = MockWebAssistant()
        ws_assistant.iter_messages = functools.partial(ws_assistant.iter_messages, data=response)

        self.data_source._ws_assistant = ws_assistant

        with patch.object(
                CoinbaseAdvancedTradeAPIUserStreamDataSource,
                "_decipher_message"
        ) as mock_decipher_message:
            await self.data_source._process_websocket_messages(
                self.data_source._ws_assistant,  # type: ignore
                queue
            )

        self.assertEqual(1, ws_assistant.iter_messages_count)
        mock_decipher_message.assert_called_once_with(event_message=data)

    async def test_decipher_message(self):
        self.data_source.logger = MagicMock()
        self.data_source._connector = MagicMock()
        self.data_source._connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USD")

        with patch('hummingbot.connector.exchange.coinbase_advanced_trade'
                   '.coinbase_advanced_trade_api_user_stream_data_source.get_timestamp_from_exchange_time',
                   return_value=1678900000):
            async for cumulative_order in self.data_source._decipher_message(self.event_message):
                self.assertIsInstance(cumulative_order, CoinbaseAdvancedTradeCumulativeUpdate)
                self.assertEqual(cumulative_order, self.cumulative_update)


class TestMessageToCumulativeUpdate(IsolatedAsyncioWrapperTestCase):

    async def test_valid_message(self):
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade'
                   '.coinbase_advanced_trade_api_user_stream_data_source.get_timestamp_from_exchange_time',
                   return_value=1678900000):
            cb_user_data_stream = AsyncMock(spec=CoinbaseAdvancedTradeAPIUserStreamDataSource)
            cb_user_data_stream._connector = AsyncMock(spec=CoinbaseAdvancedTradeExchange)
            cb_user_data_stream._connector.trading_pair_associated_to_exchange_symbol.return_value = "BTC-USD"
            cb_user_data_stream._decipher_message = functools.partial(
                CoinbaseAdvancedTradeAPIUserStreamDataSource._decipher_message,
                cb_user_data_stream
            )
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
            async for cumulative_order in cb_user_data_stream._decipher_message(event_message):
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
            cb_user_data_stream = AsyncMock(spec=CoinbaseAdvancedTradeAPIUserStreamDataSource)
            cb_user_data_stream._connector = AsyncMock(spec=CoinbaseAdvancedTradeExchange)
            cb_user_data_stream._decipher_message = functools.partial(
                CoinbaseAdvancedTradeAPIUserStreamDataSource._decipher_message,
                cb_user_data_stream
            )

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
                                "cumulative_quantity": "invalid",  # <-
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
            with self.assertRaises(decimal.InvalidOperation):
                async for _ in cb_user_data_stream._decipher_message(event_message):
                    pass


if __name__ == '__main__':
    unittest.main()
