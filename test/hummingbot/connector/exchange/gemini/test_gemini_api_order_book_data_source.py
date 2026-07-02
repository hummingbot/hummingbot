import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_api_order_book_data_source import GeminiAPIOrderBookDataSource
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class GeminiAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = "btcusd"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.connector = GeminiExchange(
            gemini_api_key="",
            gemini_api_secret="",
            trading_pairs=[self.trading_pair],
            trading_required=False)
        self.data_source = GeminiAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _snapshot_response(self):
        return {
            "bids": [
                {"price": "9", "amount": "1", "timestamp": "1500000000"},
            ],
            "asks": [
                {"price": "11", "amount": "2", "timestamp": "1500000000"},
            ],
        }

    def _trade_event(self):
        return {
            "type": "trade",
            "symbol": "BTCUSD",
            "event_id": 1,
            "timestamp": 1700000000000,
            "E": 1700000000000000000,
            "s": self.ex_trading_pair,
            "t": 12345,
            "p": "10.0",
            "q": "0.5",
            "m": False,
        }

    def _diff_event(self):
        return {
            "e": CONSTANTS.WS_EVENT_DEPTH_UPDATE,
            "s": self.ex_trading_pair,
            "U": 100,
            "u": 110,
            "b": [["9", "1"]],
            "a": [["11", "2"]],
        }

    # ------------------------------------------------------------------
    # REST snapshot
    # ------------------------------------------------------------------

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(self.ex_trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(9, bids[0].price)
        self.assertEqual(1, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(11, asks[0].price)
        self.assertEqual(2, asks[0].amount)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(self.ex_trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    async def test_get_last_traded_prices_delegates_to_connector(self):
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 10.0})
        result = await self.data_source.get_last_traded_prices([self.trading_pair])
        self.assertEqual({self.trading_pair: 10.0}, result)

    # ------------------------------------------------------------------
    # WS subscriptions
    # ------------------------------------------------------------------

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps({"result": None, "id": 1}))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)
        self.assertEqual(2, len(sent))
        self.assertEqual([CONSTANTS.WS_TRADE_STREAM.format(self.ex_trading_pair)], sent[0]["params"])
        self.assertEqual([CONSTANTS.WS_DEPTH_STREAM.format(self.ex_trading_pair)], sent[1]["params"])
        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book and trade channels..."))

    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws):
        mock_ws.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.resume_test_event.wait()
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("Test Error"))
        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred subscribing to order book trading and delta streams..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connected_websocket_assistant(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws = await self.data_source._connected_websocket_assistant()
        self.assertIsNotNone(ws)
        ws_connect_mock.assert_called_once()

    # ------------------------------------------------------------------
    # Message parsing
    # ------------------------------------------------------------------

    async def test_parse_trade_message_queues_message(self):
        queue = asyncio.Queue()
        await self.data_source._parse_trade_message(self._trade_event(), queue)
        msg: OrderBookMessage = queue.get_nowait()
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])

    async def test_parse_trade_message_skips_subscription_ack(self):
        queue = asyncio.Queue()
        await self.data_source._parse_trade_message({"result": None, "id": 1}, queue)
        await self.data_source._parse_trade_message({"id": 1}, queue)
        self.assertEqual(0, queue.qsize())

    async def test_parse_order_book_diff_message_queues_message(self):
        queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message(self._diff_event(), queue)
        msg: OrderBookMessage = queue.get_nowait()
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])

    async def test_parse_order_book_diff_message_skips_non_depth(self):
        queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message({"result": None}, queue)
        await self.data_source._parse_order_book_diff_message({"id": 5}, queue)
        await self.data_source._parse_order_book_diff_message({"e": "other", "s": self.ex_trading_pair}, queue)
        self.assertEqual(0, queue.qsize())

    def test_channel_originating_message(self):
        self.assertEqual(
            self.data_source._diff_messages_queue_key,
            self.data_source._channel_originating_message({"e": CONSTANTS.WS_EVENT_DEPTH_UPDATE}))
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"t": 123}))
        self.assertEqual("", self.data_source._channel_originating_message({"result": None}))

    # ------------------------------------------------------------------
    # Dynamic (un)subscribe
    # ------------------------------------------------------------------

    async def test_subscribe_to_trading_pair_no_ws(self):
        self.data_source._ws_assistant = None
        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertFalse(result)
        self.assertTrue(self._is_logged(
            "WARNING", f"Cannot subscribe to {self.trading_pair}: WebSocket not connected"))

    async def test_subscribe_to_trading_pair_successful(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        self.data_source._ws_assistant = mock_ws
        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertTrue(result)
        mock_ws.send.assert_awaited_once()

    async def test_subscribe_to_trading_pair_handles_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("boom"))
        self.data_source._ws_assistant = mock_ws
        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)
        self.assertFalse(result)

    async def test_unsubscribe_from_trading_pair_no_ws(self):
        self.data_source._ws_assistant = None
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertFalse(result)
        self.assertTrue(self._is_logged(
            "WARNING", f"Cannot unsubscribe from {self.trading_pair}: WebSocket not connected"))

    async def test_unsubscribe_from_trading_pair_successful(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        self.data_source._ws_assistant = mock_ws
        self.data_source.add_trading_pair(self.trading_pair)
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertTrue(result)
        mock_ws.send.assert_awaited_once()

    async def test_unsubscribe_from_trading_pair_handles_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("boom"))
        self.data_source._ws_assistant = mock_ws
        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)
        self.assertFalse(result)

    def test_get_next_subscribe_id_increments(self):
        first = GeminiAPIOrderBookDataSource._get_next_subscribe_id()
        second = GeminiAPIOrderBookDataSource._get_next_subscribe_id()
        self.assertEqual(first + 1, second)
