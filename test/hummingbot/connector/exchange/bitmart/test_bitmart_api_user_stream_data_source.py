import asyncio
import json
from unittest import TestCase
from unittest.mock import patch, AsyncMock

from hummingbot.connector.exchange.bitmart.bitmart_api_user_stream_data_source import BitmartAPIUserStreamDataSource
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BitmartAPIUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.api_key = 'testAPIKey'
        self.secret = 'testSecret'
        self.memo = '001'

        self.account_id = 528
        self.username = 'hbot'
        self.oms_id = 1
        self.log_records = []
        self.listening_task = None

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = BitmartAuth(api_key=self.api_key,
                                     secret_key=self.secret,
                                     memo=self.memo)
        self.data_source = BitmartAPIUserStreamDataSource(throttler, auth_assistant)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._trading_pairs = ["HBOT-USDT"]

        self.mocking_assistant = NetworkMockingAssistant()

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

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        initial_last_recv_time = self.data_source.last_recv_time

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_text_message(
            ws_connect_mock.return_value,
            json.dumps({"event": "login"}))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_text_message(ws_connect_mock.return_value, json.dumps('dummyMessage'))

        first_received_message = asyncio.get_event_loop().run_until_complete(messages.get())

        self.assertEqual('dummyMessage', first_received_message)

        self.assertTrue(self._is_logged('INFO', "Authenticating to User Stream..."))
        self.assertTrue(self._is_logged('INFO', "Successfully authenticated to User Stream."))
        self.assertTrue(self._is_logged('INFO', "Successfully subscribed to all Private channels."))

        sent_messages = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(2, len(sent_messages))
        auth_req = json.loads(sent_messages[0])
        sub_req = json.loads(sent_messages[1])
        self.assertTrue("op" in auth_req and "args" in auth_req and "testAPIKey" in auth_req["args"])
        self.assertEqual({"op": "subscribe", "args": ["spot/user/order:HBOT_USDT"]},
                         sub_req)
        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_fails_when_authentication_fails(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_text_message(
            ws_connect_mock.return_value,
            json.dumps({"errorCode": "test code", "errorMessage": "test err message"})
        )
        try:
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass
        self.assertTrue(self._is_logged("ERROR", "WebSocket login errored with message: test err message"))
        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream."))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error with BitMart WebSocket connection. "
                                                 "Retrying after 30 seconds..."))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_initialization(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if "testAPIKey" in sent_message
            else self.mocking_assistant._sent_websocket_text_messages[ws_connect_mock.return_value].append(
                sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_events_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if "order:HBOT_USDT" in sent_message
            else self.mocking_assistant._sent_websocket_text_messages[ws_connect_mock.return_value].append(sent_message)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_text_message(
                ws_connect_mock.return_value,
                json.dumps({"event": "login"})
            )
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_initialization(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception
        with self.assertRaises(Exception):
            self.listening_task = asyncio.get_event_loop().create_task(self.data_source._init_websocket_connection())
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occured with BitMart WebSocket Connection"))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if "testAPIKey" in sent_message
            else self.mocking_assistant._sent_websocket_text_messages[ws_connect_mock.return_value].append(sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream."))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error with BitMart WebSocket connection. "
                                                 "Retrying after 30 seconds..."))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_during_events_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if "order:HBOT_USDT" in sent_message
            else self.mocking_assistant._sent_websocket_text_messages[ws_connect_mock.return_value].append(sent_message)
        )
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_text_message(
                ws_connect_mock.return_value,
                json.dumps({"event": "login"}))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occured during subscribing to Bitmart private channels."))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error with BitMart WebSocket connection. "
                                                 "Retrying after 30 seconds..."))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_timeout_inner_message(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_text_message(
            ws_connect_mock.return_value,
            json.dumps({"event": "login"}))

        self.mocking_assistant.add_websocket_text_message(ws_connect_mock.return_value, json.dumps('dummyMessage'))

    def _raise_asyncio_timeout_exception(self):
        raise asyncio.TimeoutError()
