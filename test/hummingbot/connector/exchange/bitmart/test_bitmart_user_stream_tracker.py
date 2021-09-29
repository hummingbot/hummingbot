import asyncio
import json
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.connector.exchange.bitmart.bitmart_user_stream_tracker import BitmartUserStreamTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BitmartUserStreamTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = BitmartAuth(api_key='testAPIKey',
                                     secret_key='testSecret',
                                     memo="hbot")
        self.tracker = BitmartUserStreamTracker(throttler, auth_assistant)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    async def _get_next_received_message(self):
        return await self.ws_incoming_messages.get()

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.recv.side_effect = self._get_next_received_message
        return ws

    def _authentication_response(self, authenticated: bool) -> str:
        message = {"event": "login"}
        return json.dumps(message)

    def _add_successful_authentication_response(self):
        self.ws_incoming_messages.put_nowait(self._authentication_response(True))

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self._create_ws_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.tracker.start())
        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait(json.dumps('dummyMessage'))

        first_received_message = asyncio.get_event_loop().run_until_complete(self.tracker.user_stream.get())

        self.assertEqual('dummyMessage', first_received_message)
