import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import patch, AsyncMock

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS

from hummingbot.connector.exchange.ndax.ndax_api_user_stream_data_source import NdaxAPIUserStreamDataSource
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class NdaxAPIUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.uid = '001'
        self.api_key = 'testAPIKey'
        self.secret = 'testSecret'
        self.account_id = 528
        self.username = 'hbot'
        self.oms_id = 1
        self.log_records = []
        self.listening_task = None

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = NdaxAuth(uid=self.uid,
                                  api_key=self.api_key,
                                  secret_key=self.secret,
                                  account_name=self.username)
        self.data_source = NdaxAPIUserStreamDataSource(throttler, auth_assistant)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _authentication_response(self, authenticated: bool) -> str:
        user = {"UserId": 492,
                "UserName": "hbot",
                "Email": "hbot@mailinator.com",
                "EmailVerified": True,
                "AccountId": self.account_id,
                "OMSId": self.oms_id,
                "Use2FA": True}
        payload = {"Authenticated": authenticated,
                   "SessionToken": "74e7c5b0-26b1-4ca5-b852-79b796b0e599",
                   "User": user,
                   "Locked": False,
                   "Requires2FA": False,
                   "EnforceEnable2FA": False,
                   "TwoFAType": None,
                   "TwoFAToken": None,
                   "errormsg": None}
        message = {"m": 1,
                   "i": 1,
                   "n": CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME,
                   "o": json.dumps(payload)}

        return json.dumps(message)

    def _raise_exception(self, exception_class):
        raise exception_class

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        initial_last_recv_time = self.data_source.last_recv_time

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._authentication_response(True))
        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps('dummyMessage'))

        first_received_message = self.async_run_with_timeout(messages.get())

        self.assertEqual('dummyMessage', first_received_message)

        self.assertTrue(self._is_logged('INFO', "Authenticating to User Stream..."))
        self.assertTrue(self._is_logged('INFO', "Successfully authenticated to User Stream."))
        self.assertTrue(self._is_logged('INFO', "Successfully subscribed to user events."))

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(2, len(sent_messages))
        authentication_request = sent_messages[0]
        subscription_request = sent_messages[1]
        self.assertEqual(CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME,
                         NdaxWebSocketAdaptor.endpoint_from_raw_message(json.dumps(authentication_request)))
        self.assertEqual(CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME,
                         NdaxWebSocketAdaptor.endpoint_from_raw_message(json.dumps(subscription_request)))
        subscription_payload = NdaxWebSocketAdaptor.payload_from_raw_message(json.dumps(subscription_request))
        expected_payload = {"AccountId": self.account_id,
                            "OMSId": self.oms_id}
        self.assertEqual(expected_payload, subscription_payload)

        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_fails_when_authentication_fails(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._authentication_response(False))

        try:
            self.async_run_with_timeout(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream "
                                                 "(Could not authenticate websocket connection with NDAX)"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. "
                                        "(Could not authenticate websocket connection with NDAX)"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_initialization(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            self.async_run_with_timeout(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME in sent_message['n']
            else self.mocking_assistant._sent_websocket_json_messages[ws_connect_mock.return_value].append(sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            self.async_run_with_timeout(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_events_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME in sent_message['n']
            else self.mocking_assistant._sent_websocket_json_messages[ws_connect_mock.return_value].append(sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_aiohttp_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            self.async_run_with_timeout(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_initialization(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception

        with self.assertRaises(Exception):
            self.listening_task = asyncio.get_event_loop().create_task(self.data_source._init_websocket_connection())
            self.async_run_with_timeout(self.listening_task)
        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occurred during ndax WebSocket Connection ()"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME in sent_message['n']
            else self.mocking_assistant._sent_websocket_json_messages[ws_connect_mock.return_value].append(sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            self.async_run_with_timeout(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. ()"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_logs_exception_during_events_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME in sent_message['n'] and self._raise_exception(Exception))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_aiohttp_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            self.async_run_with_timeout(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred subscribing to ndax private channels ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. ()"))
