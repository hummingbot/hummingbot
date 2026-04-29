import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_api_order_book_data_source import GeminiAPIOrderBookDataSource
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class GeminiAPIOrderBookDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset.lower()}{cls.quote_asset.lower()}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.connector = GeminiExchange(
            gemini_api_key="",
            gemini_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.data_source = GeminiAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
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
                {"price": "4.00000000", "amount": "431.00000000", "timestamp": "1640000000"},
            ],
            "asks": [
                {"price": "4.00000200", "amount": "12.00000000", "timestamp": "1640000000"},
            ],
        }

    def _l2_update_event(self):
        return {
            "type": "l2_updates",
            "symbol": self.ex_trading_pair.upper(),
            "changes": [
                ["buy", "4.00000000", "500.00000000"],
                ["sell", "4.00000200", "15.00000000"],
            ],
            "trades": [],
        }

    def _trade_event(self):
        return {
            "type": "l2_updates",
            "symbol": self.ex_trading_pair.upper(),
            "changes": [],
            "trades": [
                {
                    "type": "trade",
                    "side": "buy",
                    "price": "4.00000100",
                    "quantity": "10.00000000",
                    "tid": 12345,
                    "timestamp": 1640000001000,
                },
            ],
        }

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        symbol = self.ex_trading_pair
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(symbol=symbol),
            domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4, bids[0].price)
        self.assertEqual(431, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertAlmostEqual(4.000002, asks[0].price, places=6)
        self.assertEqual(12, asks[0].amount)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        symbol = self.ex_trading_pair
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(symbol=symbol),
            domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_l2(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe = {"type": "l2_updates", "changes": [], "trades": []}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription = {
            "type": "subscribe",
            "subscriptions": [{"name": "l2", "symbols": [self.ex_trading_pair.upper()]}],
        }
        self.assertEqual(expected_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
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

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        self.data_source._ws_assistant = mock_ws

        with patch.object(self.connector, 'exchange_symbol_associated_to_pair', side_effect=Exception("Test Error")):
            with self.assertRaises(Exception):
                await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_successful(self):
        # Trades are extracted inside _parse_order_book_diff_message (from the
        # diff queue), so verify that path produces trade messages correctly.
        msg_queue: asyncio.Queue = asyncio.Queue()
        trade_event = self._trade_event()
        await self.data_source._parse_order_book_diff_message(trade_event, msg_queue)

        msg: OrderBookMessage = await msg_queue.get()
        self.assertEqual(12345, msg.trade_id)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._l2_update_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertIsNotNone(msg)
        self.assertEqual(2, len(msg.bids) + len(msg.asks))

    @aioresponses()
    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        symbol = self.ex_trading_pair
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(symbol=symbol),
            domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @aioresponses()
    async def test_listen_for_order_book_snapshots_successful(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        symbol = self.ex_trading_pair
        url = web_utils.public_rest_url(
            path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(symbol=symbol),
            domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertIsNotNone(msg)

    def test_channel_originating_message_trade(self):
        # All l2_updates messages (even trade-only ones) route to the diff
        # queue; trades are extracted inside _parse_order_book_diff_message.
        event = self._trade_event()
        channel = self.data_source._channel_originating_message(event)
        self.assertEqual(CONSTANTS.DIFF_EVENT_TYPE, channel)

    def test_channel_originating_message_diff(self):
        event = self._l2_update_event()
        channel = self.data_source._channel_originating_message(event)
        self.assertEqual(CONSTANTS.DIFF_EVENT_TYPE, channel)

    def test_channel_originating_message_unknown(self):
        event = {"type": "unknown"}
        channel = self.data_source._channel_originating_message(event)
        self.assertEqual("", channel)

    async def test_subscribe_to_trading_pair_successful(self):
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)

        self.assertTrue(result)
        self.assertEqual(1, mock_ws.send.call_count)

    async def test_subscribe_to_trading_pair_websocket_not_connected(self):
        self.data_source._ws_assistant = None

        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("WARNING", f"Cannot subscribe to {self.trading_pair}: WebSocket not connected")
        )

    async def test_subscribe_to_trading_pair_raises_cancel_exception(self):
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.subscribe_to_trading_pair(self.trading_pair)

    async def test_subscribe_to_trading_pair_raises_exception_and_logs_error(self):
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.subscribe_to_trading_pair(self.trading_pair)

        self.assertFalse(result)

    async def test_unsubscribe_from_trading_pair_successful(self):
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertTrue(result)
        self.assertEqual(1, mock_ws.send.call_count)

    async def test_unsubscribe_from_trading_pair_websocket_not_connected(self):
        self.data_source._ws_assistant = None

        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("WARNING", f"Cannot unsubscribe from {self.trading_pair}: WebSocket not connected")
        )

    async def test_unsubscribe_from_trading_pair_raises_cancel_exception(self):
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError
        self.data_source._ws_assistant = mock_ws

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

    async def test_unsubscribe_from_trading_pair_raises_exception_and_logs_error(self):
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Test Error")
        self.data_source._ws_assistant = mock_ws

        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error occurred unsubscribing from {self.trading_pair}...")
        )
