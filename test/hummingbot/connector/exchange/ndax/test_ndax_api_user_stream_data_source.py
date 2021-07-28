import asyncio
import json
from unittest import TestCase
from unittest.mock import patch, AsyncMock

from hummingbot.connector.exchange.ndax.ndax_api_user_stream_data_source import NdaxAPIUserStreamDataSource
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor


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
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        self.data_source = NdaxAPIUserStreamDataSource(auth_assistant=NdaxAuth(uid=self.uid,
                                                                               api_key=self.api_key,
                                                                               secret_key=self.secret,
                                                                               account_name=self.username))
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    async def _get_next_received_message(self):
        return await self.ws_incoming_messages.get()

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.recv.side_effect = self._get_next_received_message
        return ws

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

    def _add_successful_authentication_response(self):
        self.ws_incoming_messages.put_nowait(self._authentication_response(True))

    def _add_unsuccessful_authentication_response(self):
        self.ws_incoming_messages.put_nowait(self._authentication_response(False))

    def _raise_exception(self, exception_class):
        raise exception_class

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self._create_ws_mock()
        initial_last_recv_time = self.data_source.last_recv_time

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps('dummyMessage'))

        first_received_message = asyncio.get_event_loop().run_until_complete(messages.get())

        self.assertEqual('dummyMessage', first_received_message)

        self.assertTrue(self._is_logged('INFO', "Authenticating to User Stream..."))
        self.assertTrue(self._is_logged('INFO', "Successfully authenticated to User Stream."))
        self.assertTrue(self._is_logged('INFO', "Successfully subscribed to user events."))

        self.assertEqual(2, len(self.ws_sent_messages))
        authentication_request = self.ws_sent_messages[0]
        subscription_request = self.ws_sent_messages[1]
        self.assertEqual(CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME,
                         NdaxWebSocketAdaptor.endpoint_from_raw_message(authentication_request))
        self.assertEqual(CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME,
                         NdaxWebSocketAdaptor.endpoint_from_raw_message(subscription_request))
        subscription_payload = NdaxWebSocketAdaptor.payload_from_raw_message(subscription_request)
        expected_payload = {"AccountId": self.account_id,
                            "OMSId": self.oms_id}
        self.assertEqual(expected_payload, subscription_payload)

        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_fails_when_authentication_fails(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self._create_ws_mock()
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add the authentication response for the websocket
        self._add_unsuccessful_authentication_response()

        try:
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream "
                                                 "(Could not authenticate websocket connection with NDAX)"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. "
                                        "(Could not authenticate websocket connection with NDAX)"))

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
        ws_connect_mock.return_value = self._create_ws_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME in sent_message
            else self.ws_sent_messages.append(sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_events_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self._create_ws_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME in sent_message
            else self.ws_sent_messages.append(sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            # Add the authentication response for the websocket
            self._add_successful_authentication_response()
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_initialization(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception

        with self.assertRaises(Exception):
            self.listening_task = asyncio.get_event_loop().create_task(self.data_source._init_websocket_connection())
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occurred during ndax WebSocket Connection ()"))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self._create_ws_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.AUTHENTICATE_USER_ENDPOINT_NAME in sent_message
            else self.ws_sent_messages.append(sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. ()"))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_during_events_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self._create_ws_mock()
        ws_connect_mock.return_value.send.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME in sent_message
            else self.ws_sent_messages.append(sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            # Add the authentication response for the websocket
            self._add_successful_authentication_response()
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred subscribing to ndax private channels ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with NDAX WebSocket connection. Retrying in 30 seconds. ()"))
