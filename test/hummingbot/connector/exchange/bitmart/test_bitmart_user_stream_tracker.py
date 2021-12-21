import asyncio
import json
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.connector.exchange.bitmart.bitmart_user_stream_tracker import BitmartUserStreamTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BitmartUserStreamTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.listening_task = None

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = BitmartAuth(api_key='testAPIKey',
                                     secret_key='testSecret',
                                     memo="hbot")
        self.tracker = BitmartUserStreamTracker(throttler, auth_assistant)
        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps({"event": "login"}))

        self.listening_task = asyncio.get_event_loop().create_task(
            self.tracker.start())

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            json.dumps('dummyMessage'))

        first_received_message = asyncio.get_event_loop().run_until_complete(self.tracker.user_stream.get())

        self.assertEqual('dummyMessage', first_received_message)
