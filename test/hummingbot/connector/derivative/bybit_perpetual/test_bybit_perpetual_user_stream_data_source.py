import asyncio
import json
from unittest import TestCase
from unittest.mock import patch, AsyncMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_user_stream_data_source import BybitPerpetualUserStreamDataSource
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_websocket_adaptor import BybitPerpetualWebSocketAdaptor
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BybitPerpetualUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.api_key = 'testAPIKey'
        self.secret = 'testSecret'
        self.log_records = []
        self.listening_task = None

        self.data_source = BybitPerpetualUserStreamDataSource(auth_assistant=BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret))
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        if self.data_source._session is not None:
            asyncio.get_event_loop().run_until_complete(self.data_source._session.close())
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _authentication_response(self, authenticated: bool) -> str:
        request = {"op": "auth",
                   "args": ['testAPIKey', 'testExpires', 'testSignature']}
        message = {"success": authenticated,
                   "ret_msg": "",
                   "conn_id": "testConnectionID",
                   "request": request}

        return message

    def _subscription_response(self, subscribed: bool, subscription: str) -> str:
        request = {"op": "subscribe",
                   "args": [subscription]}
        message = {"success": subscribed,
                   "ret_msg": "",
                   "conn_id": "testConnectionID",
                   "request": request}

        return message

    def _raise_exception(self, exception_class):
        raise exception_class

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        initial_last_recv_time = self.data_source.last_recv_time

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._authentication_response(True))
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            self._subscription_response(True, CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME))
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            self._subscription_response(True, CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME))
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            self._subscription_response(True, CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME))

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            json.dumps('dummyMessage'))

        asyncio.get_event_loop().run_until_complete(messages.get())

        self.assertTrue(self._is_logged('INFO', "Authenticating to User Stream..."))
        self.assertTrue(self._is_logged('INFO', "Successfully authenticated to User Stream."))
        self.assertTrue(self._is_logged('INFO', "Successful subscription to the topic ['position'] on test_url"))
        self.assertTrue(self._is_logged("INFO", "Successful subscription to the topic ['order'] on test_url"))
        self.assertTrue(self._is_logged("INFO", "Successful subscription to the topic ['execution'] on test_url"))

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(4, len(sent_messages))
        authentication_request = sent_messages[0]
        subscription_positions_request = sent_messages[1]
        subscription_orders_request = sent_messages[2]
        subscription_executions_request = sent_messages[3]

        self.assertEqual(CONSTANTS.WS_AUTHENTICATE_USER_ENDPOINT_NAME,
                         BybitPerpetualWebSocketAdaptor.endpoint_from_message(authentication_request))
        self.assertEqual(CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME,
                         BybitPerpetualWebSocketAdaptor.endpoint_from_message(subscription_positions_request))
        self.assertEqual(CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME,
                         BybitPerpetualWebSocketAdaptor.endpoint_from_message(subscription_orders_request))
        self.assertEqual(CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME,
                         BybitPerpetualWebSocketAdaptor.endpoint_from_message(subscription_executions_request))

        subscription_positions_payload = BybitPerpetualWebSocketAdaptor.payload_from_message(subscription_positions_request)
        expected_payload = {"op": "subscribe",
                            "args": ["position"]}
        self.assertEqual(expected_payload, subscription_positions_payload)

        subscription_orders_payload = BybitPerpetualWebSocketAdaptor.payload_from_message(subscription_orders_request)
        expected_payload = {"op": "subscribe",
                            "args": ["order"]}
        self.assertEqual(expected_payload, subscription_orders_payload)

        subscription_executions_payload = BybitPerpetualWebSocketAdaptor.payload_from_message(subscription_executions_request)
        expected_payload = {"op": "subscribe",
                            "args": ["execution"]}
        self.assertEqual(expected_payload, subscription_executions_payload)

        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_fails_when_authentication_fails(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages))
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            self._authentication_response(False))

        try:
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream "
                                                 "(Could not authenticate websocket connection with Bybit Perpetual)"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with Bybit Perpetual WebSocket connection on"
                                        " wss://stream.bybit.com/realtime_private. Retrying in 30 seconds. "
                                        "(Could not authenticate websocket connection with Bybit Perpetual)"))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_initialization(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.WS_AUTHENTICATE_USER_ENDPOINT_NAME in sent_message["op"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_positions_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME in sent_message["args"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_json_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_orders_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME in sent_message["args"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_json_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_executions_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(asyncio.CancelledError)
            if CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME in sent_message["args"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_json_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_initialization(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception

        with self.assertRaises(Exception):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source._create_websocket_connection("test_url"))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        self.assertTrue(
            self._is_logged(
                "NETWORK",
                "Unexpected error occurred during bybit_perpetual WebSocket Connection on test_url ()"))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_details_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.WS_AUTHENTICATE_USER_ENDPOINT_NAME in sent_message["op"]
            else self.mocking_assistant.add_websocket_json_message(sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred when authenticating to user stream ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with Bybit Perpetual WebSocket connection on"
                                        " wss://stream.bybit.com/realtime_private. Retrying in 30 seconds. ()"))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_during_positions_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME in sent_message["args"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_json_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred subscribing to bybit_perpetual private channels ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with Bybit Perpetual WebSocket connection on"
                                        " wss://stream.bybit.com/realtime_private. Retrying in 30 seconds. ()"))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_during_orders_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME in sent_message["args"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_json_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred subscribing to bybit_perpetual private channels ()"))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error with Bybit Perpetual WebSocket connection on"
                                        " wss://stream.bybit.com/realtime_private. Retrying in 30 seconds. ()"))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_logs_exception_during_executions_subscription(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = lambda sent_message: (
            self._raise_exception(Exception)
            if CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME in sent_message["args"]
            else self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, sent_message))
        # Make the close function raise an exception to finish the execution
        ws_connect_mock.return_value.close.side_effect = lambda: self._raise_exception(Exception)

        try:
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            # Add the authentication response for the websocket
            self.mocking_assistant.add_websocket_json_message(
                ws_connect_mock.return_value,
                self._authentication_response(True))
            asyncio.get_event_loop().run_until_complete(self.listening_task)
        except Exception:
            pass

        self.assertTrue(self._is_logged("ERROR", "Error occurred subscribing to bybit_perpetual private channels ()"))
        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error with Bybit Perpetual WebSocket connection on"
                            " wss://stream.bybit.com/realtime_private. Retrying in 30 seconds. ()"))
