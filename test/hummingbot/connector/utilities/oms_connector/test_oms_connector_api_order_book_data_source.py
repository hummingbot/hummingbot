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
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS
from hummingbot.connector.utilities.oms_connector.oms_connector_api_order_book_data_source import (
    OMSConnectorAPIOrderBookDataSource,
)
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.connector.utilities.oms_connector.oms_connector_exchange import OMSExchange
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import (
    OMSConnectorURLCreatorBase,
    build_api_factory,
)
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestURCreator(OMSConnectorURLCreatorBase):
    def get_rest_url(self, path_url: str) -> str:
        return "https://some.url"

    def get_ws_url(self) -> str:
        return "wss://some.url"


class TestExchange(OMSExchange):
    @property
    def name(self) -> str:
        return "test_exchange"

    @property
    def oms_id(self) -> int:
        return 1

    @property
    def domain(self):
        return ""


class OMSConnectorAPIOrderBookDataSourceTest(unittest.TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "someApiKey"
        cls.secret = "someSecret"
        cls.user_id = 20
        cls.user_name = "someUserName"
        cls.oms_id = 1
        cls.account_id = 3
        cls.pair_id = 1
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.url_provider = TestURCreator()

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = TestExchange(
            client_config_map, self.api_key, self.secret, self.user_id, trading_pairs=[self.trading_pair]
        )
        self.auth = OMSConnectorAuth(api_key=self.api_key, secret_key=self.secret, user_id=self.user_id)
        self.initialize_auth()
        api_factory = build_api_factory(auth=self.auth)
        self.data_source = OMSConnectorAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=connector,
            api_factory=api_factory,
            url_provider=self.url_provider,
            oms_id=self.oms_id,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        connector._set_trading_pair_symbol_map(bidict({str(self.pair_id): self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level
            and record.getMessage() == message
            for record in self.log_records
        )

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def initialize_auth(self):
        auth_resp = self.get_auth_success_response()
        self.auth.update_with_rest_response(auth_resp)

    def get_auth_success_response(self) -> Dict[str, Any]:
        auth_resp = {
            "Authenticated": True,
            "SessionToken": "0e8bbcbc-6ada-482a-a9b4-5d9218ada3f9",
            "User": {
                "UserId": self.user_id,
                "UserName": self.user_name,
                "Email": "",
                "EmailVerified": True,
                "AccountId": self.account_id,
                "OMSId": self.oms_id,
                "Use2FA": False,
            },
            "Locked": False,
            "Requires2FA": False,
            "EnforceEnable2FA": False,
            "TwoFAType": None,
            "TwoFAToken": None,
            "errormsg": None,
        }
        return auth_resp

    @aioresponses()
    def test_get_new_order_book_success(self, mock_api):
        url = self.url_provider.get_rest_url(CONSTANTS.REST_GET_L2_SNAPSHOT_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        update_ts_ms = 21288594
        expected_update_id = update_ts_ms
        resp = [
            [21288594, 1, update_ts_ms, 0, 0.0617018, 1, 0.0586575, self.pair_id, 0.087, 0],
            [21288594, 1, update_ts_ms, 0, 0.0617018, 1, 0.0598854, self.pair_id, 2.0, 1],
        ]
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(0.0586575, bids[0].price)
        self.assertEqual(0.087, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(0.0598854, asks[0].price)
        self.assertEqual(2, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = self.url_provider.get_rest_url(CONSTANTS.REST_GET_L2_SNAPSHOT_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        instrument_id = 1
        result_subscribe_trades = {
            CONSTANTS.MSG_SEQUENCE_FIELD: 2,
            CONSTANTS.MSG_TYPE_FIELD: CONSTANTS.RESP_MSG_TYPE,
            CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_TRADES_SUB_ENDPOINT,
            CONSTANTS.MSG_DATA_FIELD: "[]",
        }
        l2_rows = [
            [21288594, 1, 1654877612463, 0, 0.0617018, 1, 0.0586575, self.pair_id, 0.087, 0],
            [21288594, 1, 1654877612463, 0, 0.0617018, 1, 0.0598854, self.pair_id, 2.0, 1],
        ]
        result_subscribe_diffs = {
            CONSTANTS.MSG_SEQUENCE_FIELD: 4,
            CONSTANTS.MSG_TYPE_FIELD: CONSTANTS.RESP_MSG_TYPE,
            CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_L2_SUB_ENDPOINT,
            CONSTANTS.MSG_DATA_FIELD: json.dumps(l2_rows),
        }

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

        self.assertEqual(1, len(sent_subscription_messages))
        req_params = {
            CONSTANTS.OMS_ID_FIELD: self.oms_id,
            CONSTANTS.INSTRUMENT_ID_FIELD: instrument_id,
            CONSTANTS.DEPTH_FIELD: CONSTANTS.MAX_L2_SNAPSHOT_DEPTH,
        }
        expected_diff_subscription = {
            CONSTANTS.MSG_SEQUENCE_FIELD: 2,
            CONSTANTS.MSG_TYPE_FIELD: CONSTANTS.REQ_MSG_TYPE,
            CONSTANTS.MSG_ENDPOINT_FIELD: CONSTANTS.WS_L2_SUB_ENDPOINT,
            CONSTANTS.MSG_DATA_FIELD: json.dumps(req_params),
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[0])
        self.assertTrue(
            self._is_logged(
                "INFO",
                "Subscribed to public order book and trade channels..."
            )
        )

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
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

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
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "arg": {
                "channel": "trades",
                "instId": "BTC-USDT"
            },
            "data": [
                {
                    "instId": "BTC-USDT",
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange")
        )

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
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "update",
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
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange")
        )

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        ts_ms = 1654877612463
        expected_update_id = ts_ms
        diff_event = {
            "m": 3,
            "i": 0,
            "n": "Level2UpdateEvent",
            "o": [
                [21288594, 1, ts_ms, 0, 0.0617018, 1, 0.0586575, self.pair_id, 0.087, 0],
                [21288594, 1, ts_ms, 0, 0.0617018, 1, 0.0598854, self.pair_id, 2.0, 1],
            ]
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
        self.assertEqual(ts_ms * 1e-3, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(0.0586575, bids[0].price)
        self.assertEqual(0.087, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(0.0598854, asks[0].price)
        self.assertEqual(2, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_sends_ping_message_before_ping_interval_finishes(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = [asyncio.TimeoutError("Test timeout"),
                                                            asyncio.CancelledError]

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = {"n": "Ping", "o": "{}", "m": 0, "i": 4}
        self.assertEqual(expected_ping_message, sent_messages[-1])
