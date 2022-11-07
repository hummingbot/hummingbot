import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

import dateutil.parser as date_parser
from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source import LbankAPIOrderBookDataSource
from hummingbot.connector.exchange.lbank.lbank_exchange import LbankExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class LbankAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset.lower()}_{cls.quote_asset.lower()}"

    @classmethod
    def tearDownClass(cls) -> None:
        for task in asyncio.all_tasks(loop=cls.ev_loop):
            task.cancel()

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = LbankExchange(
            client_config_map=client_config_map,
            lbank_api_key="",
            lbank_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False
        )
        self.data_source = LbankAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    @patch("hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source.LbankAPIOrderBookDataSource._time")
    def test_get_new_order_book_successful(self, mock_api, mock_time):
        mock_time.return_value = 1.234
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "result": "true",
            "data": {
                "asks": [
                    ["1175.62", "1.2028"],
                    ["1175.73", "1.2028"],
                    ["1175.82", "3.941"],
                    ["1175.93", "4.29"],
                    ["1176.01", "8.292"],
                ],
                "bids": [
                    ["1175.34", "2.009"],
                    ["1175.3", "2.4356"],
                    ["1175.28", "2.839"],
                    ["1175.15", "2.5829"],
                    ["1175.01", "1.2028"],
                ],
                "timestamp": 1655368540932,
            },
            "error_code": 0,
            "ts": 1655368540932,
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = resp["data"]["timestamp"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(5, len(bids))
        self.assertEqual(5, len(asks))
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(expected_update_id, asks[0].update_id)
        self.assertEqual(1175.34, bids[0].price)
        self.assertEqual(1175.62, asks[0].price)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Simply added to resume the test.
        ping_message = {"ping": "a3b3fb88-2f09-44e0-b4f5-74289374d96d", "action": "ping"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(ping_message)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(3, len(sent_json_messages))
        expected_depth_subscription = {
            "action": "subscribe",
            "subscribe": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL,
            "depth": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL_DEPTH,
            "pair": self.ex_trading_pair,
        }
        self.assertEqual(expected_depth_subscription, sent_json_messages[0])
        expected_trade_subscription = {
            "action": "subscribe",
            "subscribe": "trade",
            "pair": self.ex_trading_pair
        }
        self.assertEqual(expected_trade_subscription, sent_json_messages[1])
        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book and trade channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_sends_pong_message_when_ping_received(self, ws_connect_mock):

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ping_message = {"ping": "a3b3fb88-2f09-44e0-b4f5-74289374d96d", "action": "ping"}

        self.mocking_assistant.add_websocket_aiohttp_message(websocket_mock=ws_connect_mock.return_value,
                                                             message=json.dumps(ping_message))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        expected_pong_message = {"action": "pong", "pong": ping_message["ping"]}
        self.assertEqual(expected_pong_message, sent_json_messages[2])  # Note first 2 msg are subscription requests

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ping_message_processing_logs_error(self, ws_connect_mock):

        ws_connect_mock.send.side_effect = RuntimeError("Test Error")

        ping_message = {"ping": "a3b3fb88-2f09-44e0-b4f5-74289374d96d", "action": "ping"}

        self.ev_loop.run_until_complete(self.data_source._handle_ping_message(
            event_message=ping_message,
            ws_assistant=ws_connect_mock,
        ))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred sending pong response to public stream connection... Error: Test Error"
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ping_message_processing_raises_cancelled_exception(self, ws_connect_mock):

        ws_connect_mock.send.side_effect = asyncio.CancelledError

        ping_message = {"ping": "a3b3fb88-2f09-44e0-b4f5-74289374d96d", "action": "ping"}

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout,
            self.data_source._handle_ping_message(event_message=ping_message, ws_assistant=ws_connect_mock)
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_error_when_ping_message_processing_fails(self, ws_connect_mock):

        ws_connect_mock.send.side_effect = RuntimeError("Test Error")

        ping_message = {"ping": "a3b3fb88-2f09-44e0-b4f5-74289374d96d", "action": "ping"}

        self.ev_loop.run_until_complete(self.data_source._handle_ping_message(
            event_message=ping_message,
            ws_assistant=ws_connect_mock,
        ))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred sending pong response to public stream connection... Error: Test Error"
            )
        )

    @patch(
        "hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source.LbankAPIOrderBookDataSource"
        "._ping_request_interval"
    )
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_sends_ping_request(self, ws_connect_mock, ping_interval_mock):
        # Change interval configuration to force the timeout
        ping_interval_mock.side_effect = [-1, asyncio.CancelledError]

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual("ping", sent_json_messages[2]["action"])  # Note first 2 msg are subscription requests
        self.assertIn("ping", sent_json_messages[2])

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
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
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
        incomplete_resp = {"arg": {"channel": "trades", "instId": "BTC-USDT"}, "data": [{"instId": "BTC-USDT"}]}

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
            "trade": {
                "volume": 0.0659,
                "amount": 77.237436,
                "price": 1172.04,
                "direction": "buy",
                "TS": "2022-06-16T17:02:27.083",
            },
            "SERVER": "V2",
            "type": "trade",
            "pair": self.ex_trading_pair,
            "TS": "2022-06-16T17:02:27.086",
        }

        expected_timestamp = date_parser.parse(trade_event["trade"]["TS"]).timestamp()
        expected_trade_id: int = int(expected_timestamp * 1e3)

        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(expected_trade_id, msg.trade_id)
        self.assertEqual(expected_timestamp, msg.timestamp)

    def test_listen_for_order_book_snapshot_events_cancelled(self):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_snapshot_events_logs_exception(self):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time

        incomplete_resp = {
            "type": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL,
            "TS": "2022-06-16T16:21:29.098",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task, timeout=2)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book snapshots from exchange")
        )

    def test_listen_for_order_book_snapshot_events_successful(self):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time

        mock_queue = AsyncMock()
        snapshot_event = {
            CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL: {
                "asks": [["1161.58", "3.7754"]],
                "bids": [["1161.47", "0.8194"]]
            },
            "count": 100,
            "type": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL,
            "pair": self.ex_trading_pair,
            "SERVER": "V2",
            "TS": "2022-06-16T16:21:29.098",
        }
        expected_msg_timestamp: float = date_parser.parse(snapshot_event["TS"]).timestamp()
        expected_update_id = int(expected_msg_timestamp * 1e3)

        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(expected_msg_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(1161.47, bids[0].price)
        self.assertEqual(0.8194, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(1161.58, asks[0].price)
        self.assertEqual(3.7754, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue()))

    @aioresponses()
    @patch("hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source.LbankAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_listen_for_order_book_http_snapshots_successful(
        self, mock_api,
    ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.LBANK_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "result": "true",
            "data": {
                "asks": [
                    ["1121.82", "2.6091"],
                ],
                "bids": [
                    ["1121.56", "2.9991"],
                ],
                "timestamp": 1655377925100,
            },
            "error_code": 0,
            "ts": 1655377925109,
        }

        expected_update_id = resp["data"]["timestamp"]
        expected_timestamp = resp["data"]["timestamp"] * 1e-3

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(1121.56, bids[0].price)
        self.assertEqual(2.9991, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(1121.82, asks[0].price)
        self.assertEqual(2.6091, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_messages_from_known_channels_are_added_to_the_correct_queues(self, ws_connect_mock):

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_event = {
            "trade": {
                "volume": 0.0659,
                "amount": 77.237436,
                "price": 1172.04,
                "direction": "buy",
                "TS": "2022-06-16T17:02:27.083",
            },
            "SERVER": "V2",
            "type": "trade",
            "pair": self.ex_trading_pair,
            "TS": "2022-06-16T17:02:27.086",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(trade_event)
        )

        snapshot_event = {
            CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL: {
                "asks": [["1161.58", "3.7754"]],
                "bids": [["1161.47", "0.8194"]]
            },
            "count": 100,
            "type": CONSTANTS.LBANK_ORDER_BOOK_DEPTH_CHANNEL,
            "pair": self.ex_trading_pair,
            "SERVER": "V2",
            "TS": "2022-06-16T16:21:29.098",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(snapshot_event)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, self.data_source._message_queue[self.data_source._trade_messages_queue_key].qsize())
        self.assertEqual(trade_event,
                         self.data_source._message_queue[self.data_source._trade_messages_queue_key].get_nowait())
        self.assertEqual(1, self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].qsize())
        self.assertEqual(snapshot_event,
                         self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].get_nowait())
