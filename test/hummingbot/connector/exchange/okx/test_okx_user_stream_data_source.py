import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import WSMessage, WSMsgType

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.okx.okx_api_user_stream_data_source import OkxAPIUserStreamDataSource
from hummingbot.connector.exchange.okx.okx_auth import OkxAuth
from hummingbot.connector.exchange.okx.okx_exchange import OkxExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class OkxUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.time_synchronizer = MagicMock()
        self.time_synchronizer.time.return_value = 1640001112.223

        self.auth = OkxAuth(
            api_key="TEST_API_KEY",
            secret_key="TEST_SECRET",
            passphrase="TEST_PASSPHRASE",
            time_provider=self.time_synchronizer)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = OkxExchange(
            client_config_map=client_config_map,
            okx_api_key="",
            okx_secret_key="",
            okx_passphrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = OkxAPIUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        successful_login_response = {
            "event": "login",
            "code": "0",
            "msg": ""
        }
        result_subscribe_orders = {
            "event": "subscribe",
            "arg": {
                "channel": "account"
            }
        }
        result_subscribe_account = {
            "event": "subscribe",
            "arg": {
                "channel": "orders",
                "instType": "SPOT",
            }
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(successful_login_response))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_account))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_messages))
        expected_login = {
            "op": "login",
            "args": [
                {
                    "apiKey": self.auth.api_key,
                    "passphrase": self.auth.passphrase,
                    'timestamp': '1640001112',
                    'sign': 'wEhbGLkjM+fzAclpjd67vGUzbRpxPe4AlLyh6/wVwL4=',
                }
            ]
        }
        self.assertEqual(expected_login, sent_messages[0])
        expected_account_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "account"
                }
            ]
        }
        self.assertEqual(expected_account_subscription, sent_messages[1])
        expected_orders_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "orders",
                    "instType": "SPOT",
                }
            ]
        }
        self.assertEqual(expected_orders_subscription, sent_messages[2])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private account and orders channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_authentication_failure(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        login_response = {
            "event": "error",
            "code": "60009",
            "msg": "Login failed."
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(login_response))

        output_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {
            "event": "login",
            "code": "0",
            "msg": ""
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value,
            json.dumps(successful_login_response))
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_sends_ping_message_before_ping_interval_finishes(
            self,
            ws_connect_mock):

        successful_login_response = {
            "event": "login",
            "code": "0",
            "msg": ""
        }

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = [
            WSMessage(type=WSMsgType.TEXT, data=json.dumps(successful_login_response), extra=None),
            asyncio.TimeoutError("Test timeout"),
            asyncio.CancelledError]

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.text_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = "ping"
        self.assertEqual(expected_ping_message, sent_messages[0])
