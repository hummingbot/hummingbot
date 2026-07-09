import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aioresponses import aioresponses

from hummingbot.connector.derivative.pacifica_perpetual import pacifica_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_api_order_book_data_source import (
    PacificaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class PacificaPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset

    def setUp(self):
        super().setUp()
        self.log_records = []
        self.async_tasks = []

        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(side_effect=lambda trading_pair: trading_pair.split('-')[0])
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=lambda symbol: f"{symbol}-USDC")
        self.connector.get_last_traded_prices = AsyncMock(return_value={"BTC-USDC": 100000.0})
        self.connector._trading_pairs = [self.trading_pair]
        self.connector.api_config_key = "test_api_key"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.async_tasks = []

        self.client_session = aiohttp.ClientSession(loop=self.local_event_loop)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.rest_connection = RESTConnection(self.client_session)
        self.rest_assistant = RESTAssistant(connection=self.rest_connection, throttler=self.throttler)
        self.ws_connection = WSConnection(self.client_session)
        self.ws_assistant = WSAssistant(connection=self.ws_connection)

        self.api_factory = MagicMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest_assistant)

        self.data_source = PacificaPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        await self.mocking_assistant.async_init()

    def tearDown(self):
        self.run_async_with_timeout(self.client_session.close())
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str):
        return any(record.levelname == log_level and message in record.getMessage() for record in self.log_records)

    def get_rest_snapshot_msg(self):
        """Mock REST order book snapshot response"""
        return {
            "success": True,
            "data": {
                "s": self.ex_trading_pair,
                "l": [
                    [
                        {"p": "105376.50", "a": "1.25"},  # Ask. price, size
                        {"p": "105380.25", "a": "0.85"},
                    ],
                    [
                        {"p": "105370.00", "a": "1.50"},  # Bid: price, size
                        {"p": "105365.00", "a": "2.00"},
                    ]
                ],
                "t": 1748954160000
            }
        }

    def get_ws_snapshot_msg(self):
        """Mock WebSocket order book snapshot message"""
        return {
            "channel": "book",
            "data": {
                "l": [
                    [
                        {"p": "105376.50", "a": "1.25"},
                        {"p": "105380.25", "a": "0.85"},
                    ],
                    [
                        {"p": "105370.00", "a": "1.50"},
                        {"p": "105365.00", "a": "2.00"},
                    ]
                ],
                "s": self.ex_trading_pair,
                "t": 1748954160000,
                "li": 1559885104
            }
        }

    def get_ws_trade_msg(self):
        """Mock WebSocket trade message"""
        return {
            "channel": "trades",
            "data": [{
                "u": "42trU9A5...",
                "h": 80062522,
                "s": self.ex_trading_pair,
                "d": "open_long",
                "p": "105400.50",
                "a": "0.15",
                "t": 1749051930502,
                "m": False,
                "li": 80062522
            }]
        }

    def get_funding_info_msg(self):
        """Mock funding info REST response"""
        return {
            "success": True,
            "data": [{
                "funding": "0.000105",
                "mark": "105400.25",
                "oracle": "105400.00",
                "symbol": self.ex_trading_pair,
                "timestamp": 1749051612681,
                "volume_24h": "63265.87522",
                "yesterday_price": "105476"
            }]
        }

    def get_funding_info_ws_msg(self):
        """Mock funding info WebSocket message"""
        return {
            "channel": "prices",
            "data": [{
                "funding": "0.000105",
                "mark": "105400.25",
                "oracle": "105400.00",
                "symbol": self.ex_trading_pair,
                "timestamp": 1749051612681
            }]
        }

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        """Test successful order book snapshot retrieval"""
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self.get_rest_snapshot_msg()))

        order_book = await self.data_source._order_book_snapshot(trading_pair=self.trading_pair)

        self.assertIsInstance(order_book, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, order_book.type)
        self.assertEqual(self.trading_pair, order_book.content["trading_pair"])

        # Verify bids and asks
        bids = order_book.content["bids"]
        asks = order_book.content["asks"]
        self.assertEqual(2, len(bids))
        self.assertEqual(2, len(asks))

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        """Test error handling when order book fetch fails"""
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=500)

        with self.assertRaises(IOError):
            await self.data_source._order_book_snapshot(trading_pair=self.trading_pair)

    @aioresponses()
    async def test_get_funding_info_successful(self, mock_api):
        """Test successful funding info retrieval"""
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.GET_PRICES_PATH_URL}"

        mock_api.get(url, body=json.dumps(self.get_funding_info_msg()))

        funding_info = await self.data_source.get_funding_info(trading_pair=self.trading_pair)

        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("105400.25"), funding_info.mark_price)
        self.assertEqual(Decimal("105400.00"), funding_info.index_price)
        self.assertAlmostEqual(0.000105, float(funding_info.rate), places=6)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_required_channels(self, ws_connect_mock):
        """Test that WebSocket subscribes to trades, orderbook, and funding channels"""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Mock subscription confirmations
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps({"channel": "subscribe", "data": {"source": "book"}})
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps({"channel": "subscribe", "data": {"source": "trades"}})
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps({"channel": "subscribe", "data": {"source": "prices"}})
        )

        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_subscriptions())
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        # Should subscribe to: book, trades, prices for each trading pair
        self.assertGreaterEqual(len(sent_messages), 3)

        channels = [msg.get("params", {}).get("source") for msg in sent_messages if "params" in msg]
        self.assertIn("book", channels)
        self.assertIn("trades", channels)
        self.assertIn("prices", channels)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_trades_successful(self, ws_connect_mock):
        """Test successful trade message parsing"""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps(self.get_ws_trade_msg())
        )

        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_subscriptions())
        )

        message_queue = asyncio.Queue()
        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_trades(asyncio.get_event_loop(), message_queue))
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, message_queue.qsize())
        trade_message = message_queue.get_nowait()

        self.assertIsInstance(trade_message, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(self.trading_pair, trade_message.content["trading_pair"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_order_book_snapshots_successful(self, ws_connect_mock):
        """Test successful order book snapshot parsing"""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps(self.get_ws_snapshot_msg())
        )

        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_subscriptions())
        )

        message_queue = asyncio.Queue()
        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), message_queue))
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, message_queue.qsize())
        snapshot_message = message_queue.get_nowait()

        self.assertIsInstance(snapshot_message, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_funding_info_successful(self, ws_connect_mock):
        """Test successful funding info parsing from WebSocket"""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps(self.get_funding_info_ws_msg())
        )

        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_subscriptions())
        )

        message_queue = asyncio.Queue()
        self.async_tasks.append(
            asyncio.create_task(self.data_source.listen_for_funding_info(message_queue))
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertGreater(message_queue.qsize(), 0)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_raises_cancel_exception(self, ws_connect_mock):
        """Test that CancelledError is properly propagated"""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        task = asyncio.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(task)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_trades_cancelled(self, ws_connect_mock):
        """Test that trade listening can be cancelled"""
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        message_queue = asyncio.Queue()
        task = asyncio.create_task(self.data_source.listen_for_trades(asyncio.get_event_loop(), message_queue))
        self.async_tasks.append(task)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_subscribe_to_trading_pair_successful(self):
        """Test successful subscription to a new trading pair"""
        self.data_source._ws_assistant = AsyncMock()
        new_pair = "ETH-USDC"

        result = await self.data_source.subscribe_to_trading_pair(new_pair)

        self.assertTrue(result)
        self.assertIn(new_pair, self.data_source._trading_pairs)

    async def test_unsubscribe_from_trading_pair_successful(self):
        """Test successful unsubscription from a trading pair"""
        self.data_source._ws_assistant = AsyncMock()
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertTrue(result)
        self.assertNotIn(self.trading_pair, self.data_source._trading_pairs)

    async def test_subscribe_to_trading_pair_fails_when_not_connected(self):
        """Test subscription fails if WebSocket is not connected"""
        self.data_source._ws_assistant = None
        new_pair = "ETH-USDC"

        result = await self.data_source.subscribe_to_trading_pair(new_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("WARNING", f"Cannot subscribe to {new_pair}: WebSocket not connected")
        )

    async def test_unsubscribe_from_trading_pair_fails_when_not_connected(self):
        """Test unsubscription fails if WebSocket is not connected"""
        self.data_source._ws_assistant = None

        await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertTrue(
            self._is_logged("WARNING", f"Cannot unsubscribe from {self.trading_pair}: WebSocket not connected")
        )

    async def test_get_last_traded_prices(self):
        self.connector.get_last_traded_prices.return_value = {"BTC-USDC": 1.23, "ETH-USDC": 1.23}
        result = await self.data_source.get_last_traded_prices(["BTC-USDC", "ETH-USDC"])
        self.assertEqual({"BTC-USDC": 1.23, "ETH-USDC": 1.23}, result)
        self.connector.get_last_traded_prices.assert_awaited_once_with(trading_pairs=["BTC-USDC", "ETH-USDC"])

    @aioresponses()
    async def test_get_funding_info_element_failure(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.GET_PRICES_PATH_URL}"

        # Case 1: success=False
        mock_api.get(url, payload={"success": False, "data": []})
        with self.assertRaises(ValueError):
            await self.data_source.get_funding_info(self.trading_pair)

        # Case 2: data is empty list
        mock_api.get(url, payload={"success": True, "data": []}, repeat=True)
        with self.assertRaises(ValueError):
            await self.data_source.get_funding_info(self.trading_pair)

    async def test_subscribe_exception_path(self):
        self.data_source._ws_assistant = self.ws_assistant
        self.ws_assistant.send = AsyncMock(side_effect=Exception("boom"))

        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertFalse(result)
        self.assertTrue(self._is_logged("ERROR", f"Error subscribing to {self.trading_pair}"))

    async def test_unsubscribe_exception_path(self):
        self.data_source._ws_assistant = self.ws_assistant
        self.ws_assistant.send = AsyncMock(side_effect=Exception("oops"))

        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertFalse(result)
        self.assertTrue(self._is_logged("ERROR", f"Error unsubscribing from {self.trading_pair}"))
