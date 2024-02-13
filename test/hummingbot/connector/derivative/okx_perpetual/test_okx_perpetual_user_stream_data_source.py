import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth import OkxPerpetualAuth
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_user_stream_data_source import (
    OkxPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class OkxPerpetualUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}-SWAP"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.time_synchronizer = MagicMock()
        self.time_synchronizer.time.return_value = 1640001112.223

        auth = OkxPerpetualAuth(api_key="TEST_API_KEY", api_secret="TEST_SECRET", passphrase="TEST_PASSPHRASE", time_provider=self.time_synchronizer)
        api_factory = web_utils.build_api_factory(auth=auth)
        self.data_source = OkxPerpetualUserStreamDataSource(
            auth=auth, api_factory=api_factory, domain=self.domain
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @staticmethod
    def _authentication_response(subscribed) -> str:
        message = {
            "event": "login" if subscribed else "error",
            "code": "0",
            "msg": "",
            "connId": "a4d3ae55"
        }
        return json.dumps(message)

    def _subscription_response(self, subscription: str) -> str:
        message = {
            "op": "subscribe",
            "args": [
                {
                    "channel": subscription,
                    "instId": self.ex_trading_pair
                }
            ]
        }

        return json.dumps(message)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        initial_last_recv_time = self.data_source.last_recv_time

        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, self._authentication_response(True))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._subscription_response(CONSTANTS.WS_POSITIONS_CHANNEL))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._subscription_response(CONSTANTS.WS_ORDERS_CHANNEL))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._subscription_response(CONSTANTS.WS_BALANCE_AND_POSITIONS_CHANNEL))

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", messages)
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to private account and orders channels test_url...")
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(4, len(sent_messages))
        authentication_request = sent_messages[0]
        subscription_positions_request = sent_messages[1]
        subscription_orders_request = sent_messages[2]
        subscription_wallet_request = sent_messages[3]

        self.assertEqual(web_utils.endpoint_from_message(authentication_request), "login")

        expected_payload = {"op": "subscribe",
                            "args": [
                                {"channel": CONSTANTS.WS_POSITIONS_CHANNEL, "instType": "SWAP"}
                            ]}
        self.assertEqual(expected_payload, subscription_positions_request)

        expected_payload = {"op": "subscribe",
                            "args": [
                                {"channel": CONSTANTS.WS_ORDERS_CHANNEL, "instType": "SWAP"}
                            ]}
        self.assertEqual(expected_payload, subscription_orders_request)

        expected_payload = {"op": "subscribe",
                            "args": [
                                {"channel": CONSTANTS.WS_ACCOUNT_CHANNEL}
                            ]}
        self.assertEqual(expected_payload, subscription_wallet_request)

        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_authentication_failure(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", messages))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._authentication_response(False))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Error authenticating the private websocket connection"))
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream test_url. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._authentication_response(True)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error while listening to user stream test_url. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_canceled_on_cancel_exception(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            self.async_run_with_timeout(self.listening_task)
