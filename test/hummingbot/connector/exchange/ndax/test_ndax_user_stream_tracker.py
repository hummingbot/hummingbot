import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS

from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_user_stream_tracker import NdaxUserStreamTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class NdaxUserStreamTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = NdaxAuth(uid='001',
                                  api_key='testAPIKey',
                                  secret_key='testSecret',
                                  account_name="hbot")
        self.tracker = NdaxUserStreamTracker(throttler=throttler, auth_assistant=auth_assistant)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _authentication_response(self, authenticated: bool) -> str:
        user = {"UserId": 492,
                "UserName": "hbot",
                "Email": "hbot@mailinator.com",
                "EmailVerified": True,
                "AccountId": 528,
                "OMSId": 1,
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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.tracker.start())
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._authentication_response(True))
        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps('dummyMessage'))

        first_received_message = self.async_run_with_timeout(self.tracker.user_stream.get())

        self.assertEqual('dummyMessage', first_received_message)
