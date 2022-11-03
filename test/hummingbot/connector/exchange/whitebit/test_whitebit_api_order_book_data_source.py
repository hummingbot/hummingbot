import asyncio
import json
import re
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.whitebit import whitebit_constants as CONSTANTS, whitebit_web_utils as web_utils
from hummingbot.connector.exchange.whitebit.whitebit_api_order_book_data_source import WhitebitAPIOrderBookDataSource
from hummingbot.connector.exchange.whitebit.whitebit_exchange import WhitebitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class WhitebitAPIOrderBookDataSourceUnitTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = WhitebitExchange(
            client_config_map=client_config_map,
            whitebit_api_key="",
            whitebit_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.data_source = WhitebitAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )
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
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_BOOK_PATH)
        url = url + f"/{self.ex_trading_pair}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "timestamp": 1594391413,
            "asks": [
                ["9184.41", "0.773162"],
            ],
            "bids": [
                ["9181.19", "0.010873"],
            ],
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = resp["timestamp"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(float(resp["bids"][0][0]), bids[0].price)
        self.assertEqual(float(resp["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(float(resp["asks"][0][0]), asks[0].price)
        self.assertEqual(float(resp["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_with_only_bids_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_BOOK_PATH)
        url = url + f"/{self.ex_trading_pair}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "timestamp": 1594391413,
            "bids": [
                ["9181.19", "0.010873"],
            ],
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = resp["timestamp"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(float(resp["bids"][0][0]), bids[0].price)
        self.assertEqual(float(resp["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(0, len(asks))

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.WHITEBIT_ORDER_BOOK_PATH)
        url = url + f"/{self.ex_trading_pair}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {"id": 2, "result": {"status": "success"}, "error": None}
        result_subscribe_diffs = {"id": 1, "result": {"status": "success"}, "error": None}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_trades)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(result_subscribe_diffs)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_subscription_messages))
        expected_diff_subscription = {
            "id": 1,
            "method": "depth_subscribe",
            "params": [
                self.ex_trading_pair,
                100,
                "0",
                True,
            ],
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[0])

        expected_trade_subscription = {
            "id": 2,
            "method": "trades_subscribe",
            "params": [
                self.ex_trading_pair,
            ],
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book and trade channels..."))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
            )
        )

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {"id": None, "method": CONSTANTS.WHITEBIT_WS_PUBLIC_TRADES_CHANNEL, "params": []}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PUBLIC_TRADES_CHANNEL,
            "params": [
                self.ex_trading_pair,
                [
                    {
                        "id": 41358530,
                        "time": 1580905394.70332,
                        "price": "0.020857",
                        "amount": "5.511",
                        "type": "buy",
                    },
                ],
            ],
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_event["params"][1][0]["id"], msg.trade_id)
        self.assertEqual(float(trade_event["params"][1][0]["time"]), msg.timestamp)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {"id": None, "method": CONSTANTS.WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL, "params": []}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange")
        )

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._time")
    def test_listen_for_order_book_diffs_successful(self, time_mock):
        time_mock.side_effect = [1655749683.225128, 1656749683, 1657749683]
        mock_queue = AsyncMock()
        diff_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL,
            "params": [
                False,
                {"asks": [["0.020861", "0"]], "bids": [["0.020844", "5.949"], ["0.020800", "4"]]},
                self.ex_trading_pair,
            ],
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1655749683.225128, msg.timestamp)
        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_update_id = 1655749683.225128 * 1e6
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(float(diff_event["params"][1]["bids"][0][0]), bids[0].price)
        self.assertEqual(float(diff_event["params"][1]["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(float(diff_event["params"][1]["asks"][0][0]), asks[0].price)
        self.assertEqual(float(diff_event["params"][1]["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._time")
    def test_listen_for_order_book_diffs_with_only_asks_successful(self, time_mock):
        time_mock.side_effect = [1655749683.225128, 1656749683, 1657749683]
        mock_queue = AsyncMock()
        diff_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL,
            "params": [
                False,
                {
                    "asks": [["0.020861", "0"]],
                },
                self.ex_trading_pair,
            ],
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1655749683.225128, msg.timestamp)
        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_update_id = 1655749683.225128 * 1e6
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(0, len(bids))
        self.assertEqual(1, len(asks))
        self.assertEqual(float(diff_event["params"][1]["asks"][0][0]), asks[0].price)
        self.assertEqual(float(diff_event["params"][1]["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._time")
    def test_listen_for_order_book_diffs_process_full_snapshot_correctly(self, time_mock):
        time_mock.side_effect = [1655749683.225128, 1656749683, 1657749683]
        mock_queue = AsyncMock()

        snapshot_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL,
            "params": [
                True,
                {"asks": [["0.020861", "20"]], "bids": [["0.020844", "5.950"], ["0.020800", "4.1"]]},
                self.ex_trading_pair,
            ],
        }

        diff_event = {
            "id": None,
            "method": CONSTANTS.WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL,
            "params": [
                False,
                {"asks": [["0.020861", "0"]], "bids": [["0.020844", "5.949"], ["0.020800", "4"]]},
                self.ex_trading_pair,
            ],
        }
        mock_queue.get.side_effect = [snapshot_event, diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1655749683.225128, msg.timestamp)
        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_update_id = 1655749683.225128 * 1e6
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(float(snapshot_event["params"][1]["bids"][0][0]), bids[0].price)
        self.assertEqual(float(snapshot_event["params"][1]["bids"][0][1]), bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(float(snapshot_event["params"][1]["asks"][0][0]), asks[0].price)
        self.assertEqual(float(snapshot_event["params"][1]["asks"][0][1]), asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)
