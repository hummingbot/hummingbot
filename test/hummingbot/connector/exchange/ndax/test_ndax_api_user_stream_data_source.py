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
        self.oms_id = 1
        self.log_records = []
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()

        self.data_source = NdaxAPIUserStreamDataSource(auth_assistant=NdaxAuth(uid=self.uid,
                                                                               api_key=self.api_key,
                                                                               secret_key=self.secret))
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

    def _add_successful_authentication_response(self):
        user = {"UserId": 492,
                "UserName": "hbot",
                "Email": "hbot@mailinator.com",
                "EmailVerified": True,
                "AccountId": self.account_id,
                "OMSId": self.oms_id,
                "Use2FA": True}
        payload = {"Authenticated": True,
                   "SessionToken": "74e7c5b0-26b1-4ca5-b852-79b796b0e599",
                   "User": json.dumps(user),
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

        self.ws_incoming_messages.put_nowait(json.dumps(message))

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
                         NdaxWebSocketAdaptor(None).endpoint_from_raw_message(authentication_request))
        self.assertEqual(CONSTANTS.SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME,
                         NdaxWebSocketAdaptor(None).endpoint_from_raw_message(subscription_request))
        subscription_payload = NdaxWebSocketAdaptor(None).payload_from_raw_message(subscription_request)
        expected_payload = {"AccountId": self.account_id,
                            "OMSId": self.oms_id}
        self.assertEqual(expected_payload, subscription_payload)

        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)
