import asyncio
import json
import unittest

from typing import Awaitable, List
from unittest.mock import AsyncMock, patch

import aiohttp

import hummingbot.connector.exchange.huobi.huobi_constants as CONSTANTS

from hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source import HuobiAPIUserStreamDataSource
from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth
from hummingbot.connector.exchange.huobi.huobi_utils import build_api_factory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class HuobiAPIUserStreamDataSourceTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.auth = HuobiAuth("somKey", "someSecretKey")
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

        self.api_factory = build_api_factory()
        self.data_source = HuobiAPIUserStreamDataSource(huobi_auth=self.auth, api_factory=self.api_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def test_get_ws_assistant(self):

        data_source = HuobiAPIUserStreamDataSource(self.auth)

        self.assertIsNone(data_source._ws_assistant)

        initial_ws_assistant = self.async_run_with_timeout(data_source._get_ws_assistant())
        self.assertIsNotNone(data_source._ws_assistant)
        self.assertIsInstance(initial_ws_assistant, WSAssistant)

        subsequent_ws_assistant = self.async_run_with_timeout(data_source._get_ws_assistant())
        self.assertEqual(initial_ws_assistant, subsequent_ws_assistant)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_authenticate_client_raises_cancelled(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = asyncio.CancelledError

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._authenticate_client())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_authenticate_client_logs_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)

        ws_connect_mock.return_value.send_json.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.data_source._authenticate_client())

        self._is_logged("ERROR", "Error occurred authenticating websocket connection... Error: TEST ERROR")

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_authenticate_client_failed(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)

        error_auth_response = {"action": "req", "code": 0, "TEST_ERROR": "ERROR WITH AUTHENTICATION"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(error_auth_response)
        )

        with self.assertRaisesRegex(ValueError, "User Stream Authentication Fail!"):
            self.async_run_with_timeout(self.data_source._authenticate_client())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_authenticate_client_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)

        successful_auth_response = {"action": "req", "code": 200, "ch": "auth", "data": {}}

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_auth_response)
        )

        result = self.async_run_with_timeout(self.data_source._authenticate_client())

        self.assertIsNone(result)
        self._is_logged("INFO", "Successfully authenticated to user...")

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_raises_cancelled(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = asyncio.CancelledError

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._subscribe_channels())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_subscribe_topic_fail(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)

        error_sub_response = {"action": "sub", "code": 0, "TEST_ERROR": "ERROR SUBSCRIBING TO USER STREAM TOPIC"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(error_sub_response)
        )

        with self.assertRaisesRegex(ValueError, "Error subscribing to topic: "):
            self.async_run_with_timeout(self.data_source._subscribe_channels())

        self._is_logged("ERROR", f"Cannot subscribe to user stream topic: {CONSTANTS.HUOBI_ORDER_UPDATE_TOPIC}")

        self._is_logged("ERROR", "Unexpected error occurred subscribing to private user streams...")

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Initialise WSAssistant and assume connected to websocket server
        self.async_run_with_timeout(self.data_source._get_ws_assistant())
        self.async_run_with_timeout(self.data_source._ws_assistant.connect(CONSTANTS.WS_PRIVATE_URL))

        self.assertIsNotNone(self.data_source._ws_assistant)
        successful_sub_trades_response = {"action": "sub", "code": 200, "ch": "trade.clearing#*", "data": {}}
        successful_sub_order_response = {"action": "sub", "code": 200, "ch": "orders#*", "data": {}}
        successful_sub_account_response = {"action": "sub", "code": 200, "ch": "accounts.update#2", "data": {}}

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_trades_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_order_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_account_response)
        )

        result = self.async_run_with_timeout(self.data_source._subscribe_channels())

        self.assertIsNone(result)

        subscription_requests_sent = self.mocking_assistant.json_messages_sent_through_websocket(
            ws_connect_mock.return_value)

        expected_orders_channel_subscription = {"action": "sub", "ch": "orders#*"}
        self.assertIn(expected_orders_channel_subscription, subscription_requests_sent)
        expected_accounts_channel_subscription = {"action": "sub", "ch": "accounts.update#2"}
        self.assertIn(expected_accounts_channel_subscription, subscription_requests_sent)
        expected_trades_channel_subscription = {"action": "sub", "ch": "trade.clearing#*"}
        self.assertIn(expected_trades_channel_subscription, subscription_requests_sent)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source.HuobiAPIUserStreamDataSource._sleep")
    def test_listen_for_user_stream_raises_cancelled_error(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.side_effect = asyncio.CancelledError

        msg_queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source.HuobiAPIUserStreamDataSource._sleep")
    def test_listen_for_user_stream_logs_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        successful_auth_response = {"action": "req", "code": 200, "ch": "auth", "data": {}}
        successful_sub_trades_response = {"action": "sub", "code": 200, "ch": "trade.clearing#*", "data": {}}
        successful_sub_order_response = {"action": "sub", "code": 200, "ch": "orders#*", "data": {}}
        successful_sub_account_response = {"action": "sub", "code": 200, "ch": "accounts.update#2", "data": {}}

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_auth_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_trades_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_order_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_account_response)
        )

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSE
        )
        msg_queue = asyncio.Queue()

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self._is_logged("ERROR", "Unexpected error with Huobi WebSocket connection. Retrying after 30 seconds...")

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source.HuobiAPIUserStreamDataSource._sleep")
    def test_listen_for_user_stream_handle_ping(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        successful_auth_response = {"action": "req", "code": 200, "ch": "auth", "data": {}}
        successful_sub_trades_response = {"action": "sub", "code": 200, "ch": "trade.clearing#*", "data": {}}
        successful_sub_order_response = {"action": "sub", "code": 200, "ch": "orders#*", "data": {}}
        successful_sub_account_response = {"action": "sub", "code": 200, "ch": "accounts.update#2", "data": {}}

        ping_response = {"action": "ping", "data": {"ts": 1637553193021}}

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_auth_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_trades_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_order_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_account_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(ping_response)
        )

        msg_queue = asyncio.Queue()

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, msg_queue.qsize())
        sent_json = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertTrue(any(["pong" in str(payload) for payload in sent_json]))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source.HuobiAPIUserStreamDataSource._sleep")
    def test_listen_for_user_stream_enqueues_updates(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        successful_auth_response = {"action": "req", "code": 200, "ch": "auth", "data": {}}
        successful_sub_trades_response = {"action": "sub", "code": 200, "ch": "trade.clearing#*", "data": {}}
        successful_sub_order_response = {"action": "sub", "code": 200, "ch": "orders#*", "data": {}}
        successful_sub_account_response = {"action": "sub", "code": 200, "ch": "accounts.update#2", "data": {}}

        ping_response = {"action": "ping", "data": {"ts": 1637553193021}}

        order_update_response = {
            "action": "push",
            "ch": "orders#",
            "data": {
                "execAmt": "0",
                "lastActTime": 1637553210074,
                "orderSource": "spot-api",
                "remainAmt": "0.005",
                "orderPrice": "4122.62",
                "orderSize": "0.005",
                "symbol": "ethusdt",
                "orderId": 414497810678464,
                "orderStatus": "canceled",
                "eventType": "cancellation",
                "clientOrderId": "AAc484720a-buy-ETH-USDT-1637553180003697",
                "type": "buy-limit-maker",
            },
        }

        account_update_response = {
            "action": "push",
            "ch": "accounts.update#2",
            "data": {
                "currency": "usdt",
                "accountId": 15026496,
                "balance": "100",
                "available": "100",
                "changeType": "order.cancel",
                "accountType": "trade",
                "seqNum": 117,
                "changeTime": 1637553210076,
            },
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_auth_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_trades_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_order_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(successful_sub_account_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(ping_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(order_update_response)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(account_update_response)
        )

        msg_queue = asyncio.Queue()

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(2, msg_queue.qsize())
