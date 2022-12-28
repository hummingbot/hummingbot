import asyncio
import json
import re
import unittest
from typing import Any, Awaitable, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.btc_markets import (
    btc_markets_constants as CONSTANTS,
    btc_markets_web_utils as web_utils,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_api_order_book_data_source import (
    BtcMarketsAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_exchange import BtcMarketsExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BtcMarketsAPIOrderBookDataSourceTest(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.api_key = "someKey"
        cls.api_secret_key = "XXXX"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task = None
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.connector = BtcMarketsExchange(
            client_config_map=self.client_config_map,
            btc_markets_api_key=self.api_key,
            btc_markets_api_secret=self.api_secret_key,
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.data_source = BtcMarketsAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        BtcMarketsAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _order_book_snapshot_example(self):
        return {
            "marketId": "BAT-AUD",
            "snapshotId": 1567334110144000,
            "bids": [["50005.12", "403.0416"]],
            "asks": [["50006.34", "0.2297"]]
        }

    def _setup_time_mock(self, mock_api):
        time_url = web_utils.public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{time_url}".replace(".", r"\.").replace("?", r"\?"))
        resp = {
            "timestamp": "2019-09-01T10:35:04.940000Z"
        }
        mock_api.get(regex_url, body=json.dumps(resp))

    def test_channel_originating_message_returns_correct(self):
        event_type = {
            "messageType": CONSTANTS.DIFF_EVENT_TYPE
        }
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._diff_messages_queue_key, event_message)

        event_type = {
            "messageType": CONSTANTS.SNAPSHOT_EVENT_TYPE
        }
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._snapshot_messages_queue_key, event_message)

        event_type = {
            "messageType": CONSTANTS.TRADE_EVENT_TYPE
        }
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._trade_messages_queue_key, event_message)

    # LAST TRADED PRICES
    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        self._setup_time_mock(mock_api)

        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKETS_URL)
        url = f"{url}/{self.ex_trading_pair}/ticker"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = {
            "marketId": self.ex_trading_pair,
            "bestBid": "0.2612",
            "bestAsk": "0.2677",
            "lastPrice": "0.265",
            "volume24h": "6392.34930418",
            "volumeQte24h": "1.39",
            "price24h": "130",
            "pricePct24h": "0.002",
            "low24h": "0.2621",
            "high24h": "0.2708",
            "timestamp": "2019-09-01T10:35:04.940000Z"
        }
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=self.data_source.get_last_traded_prices([self.trading_pair])
        )

        self.assertIn(self.trading_pair, ret)
        self.assertEqual(ret[self.trading_pair], 0.265)

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_get):
        self._setup_time_mock(mock_get)

        mock_response: Dict[str, Any] = self._order_book_snapshot_example()
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKETS_URL)
        url = f"{url}/{self.ex_trading_pair}/orderbook"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_get.get(regex_url, body=json.dumps(mock_response))

        order_book = self.async_run_with_timeout(coroutine=self.data_source.get_new_order_book(self.trading_pair))

        bid_entries = list(order_book.bid_entries())
        ask_entries = list(order_book.ask_entries())
        self.assertEqual(1, len(bid_entries))
        self.assertEqual(50005.12, bid_entries[0].price)
        self.assertEqual(403.0416, bid_entries[0].amount)
        self.assertEqual(int(mock_response["snapshotId"]), bid_entries[0].update_id)
        self.assertEqual(1, len(ask_entries))
        self.assertEqual(50006.34, ask_entries[0].price)
        self.assertEqual(0.2297, ask_entries[0].amount)
        self.assertEqual(int(mock_response["snapshotId"]), ask_entries[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subscription_result = {
            "messageType": "subscribe",
            "marketIds": [self.trading_pair],
            "channels": [CONSTANTS.DIFF_EVENT_TYPE, CONSTANTS.SNAPSHOT_EVENT_TYPE, CONSTANTS.TRADE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(subscription_result))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_trade_subscription = {
            "messageType": "subscribe",
            "marketIds": [self.ex_trading_pair],
            "channels": [CONSTANTS.DIFF_EVENT_TYPE, CONSTANTS.SNAPSHOT_EVENT_TYPE, CONSTANTS.TRADE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels for all trading pairs ..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

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
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            # "marketId": self.trading_pair,
            "timestamp": '2019-04-08T20:54:27.632Z',
            "tradeId": 3153171493,
            "price": '7370.11',
            "volume": '0.10901605',
            "side": 'Ask',
            "messageType": CONSTANTS.TRADE_EVENT_TYPE
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_queue = AsyncMock()
        trade_event = {
            "marketId": self.ex_trading_pair,
            "timestamp": '2019-04-08T20:54:27.632Z',
            "tradeId": 3153171493,
            "price": '7370.11',
            "volume": '0.10901605',
            "side": 'Ask',
            "messageType": CONSTANTS.TRADE_EVENT_TYPE
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(msg_queue.empty())
        self.assertTrue(3153171493, msg.trade_id)

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
        incomplete_resp = {
            # "marketId": self.ex_trading_pair,
            "snapshot": True,
            "snapshotId": 1578512833978000,
            "timestamp": '2020-01-08T19:47:13.986Z',
            "bids": [
                ['99.57', '0.55', 1],
                ['97.62', '3.20', 2],
                ['97.07', '0.9', 1],
                ['96.7', '1.9', 1],
                ['95.8', '7.0', 1]
            ],
            "asks": [
                ['100', '3.79', 3],
                ['101', '6.32', 2]
            ],
            "messageType": CONSTANTS.DIFF_EVENT_TYPE
        }

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
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = {
            "marketId": self.ex_trading_pair,
            "snapshot": True,
            "snapshotId": 1578512833978000,
            "timestamp": '2020-01-08T19:47:13.986Z',
            "bids": [
                ['99.57', '0.55', 1],
                ['97.62', '3.20', 2],
                ['97.07', '0.9', 1],
                ['96.7', '1.9', 1],
                ['95.8', '7.0', 1]
            ],
            "asks": [
                ['100', '3.79', 3],
                ['101', '6.32', 2]
            ],
            "messageType": CONSTANTS.DIFF_EVENT_TYPE
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(diff_event["snapshotId"], msg.update_id)

    # ORDER BOOK SNAPSHOT
    @staticmethod
    def _snapshot_response() -> Dict:
        return {
            "marketId": "COINALPHA-HBOT",
            "snapshotId": 1567334110144000,
            "bids": [
                ["50005.12", "403.0416"]
            ],
            "asks": [
                ["50006.34", "0.2297"]
            ]
        }

    @staticmethod
    def _snapshot_response_processed() -> Dict:
        return {
            "marketId": "COINALPHA-HBOT",
            "snapshotId": 1567334110144000,
            "bids": [["50005.12", "403.0416"]],
            "asks": [["50006.34", "0.2297"]]
        }

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api, sleep_mock):
        mock_response: Dict[Any] = {}
        url = web_utils.public_rest_url(f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(mock_response))

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        sleep_mock.side_effect = [asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._snapshot_response(), asyncio.CancelledError]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = [asyncio.CancelledError]
        url = web_utils.public_rest_url(f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, exception=Exception)

        try:
            self.async_run_with_timeout(self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_successful_rest(self, mock_api, _):
        self._setup_time_mock(mock_api)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.TimeoutError
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(int(snapshot_data["snapshotId"]), msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful_ws(self, mock_api):
        mock_queue = AsyncMock()
        snapshot_event = {
            "marketId": self.ex_trading_pair,
            "snapshot": True,
            "snapshotId": 1578512833978000,
            "timestamp": '2020-01-08T19:47:13.986Z',
            "bids": [
                ['99.57', '0.55', 1],
                ['97.62', '3.20', 2],
                ['97.07', '0.9', 1],
                ['96.7', '1.9', 1],
                ['95.8', '7.0', 1]
            ],
            "asks": [
                ['100', '3.79', 3],
                ['101', '6.32', 2]
            ],
            "messageType": CONSTANTS.SNAPSHOT_EVENT_TYPE
        }
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        url = web_utils.public_rest_url(f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get(), timeout=6)

        self.assertTrue(snapshot_event["snapshotId"], msg.update_id)

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_order_book_snapshot_exception(self, mock_api, sleep_mock):
        self._setup_time_mock(mock_api)

        url = web_utils.public_rest_url(path_url=f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, exception=Exception)

        self.async_run_with_timeout(self.data_source._order_book_snapshot(self.trading_pair))

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_order_book_snapshot(self, mock_api):
        self._setup_time_mock(mock_api)

        url = web_utils.public_rest_url(path_url=f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        orderbook_message = self.async_run_with_timeout(self.data_source._order_book_snapshot(self.trading_pair))

        self.assertEqual(orderbook_message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(orderbook_message.trading_pair, self.trading_pair)
        self.assertEqual(orderbook_message.content["snapshotId"], snapshot_data["snapshotId"])

    @aioresponses()
    def test_get_snapshot(self, mock_api):
        self._setup_time_mock(mock_api)

        url = web_utils.public_rest_url(path_url=f"{CONSTANTS.MARKETS_URL}/{self.ex_trading_pair}/orderbook")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        snapshot_response = self.async_run_with_timeout(self.data_source.get_snapshot(self.trading_pair))

        self.assertEqual(snapshot_response, snapshot_data)
