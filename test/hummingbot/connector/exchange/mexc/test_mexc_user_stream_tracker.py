import asyncio
from collections import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import ujson

from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
import hummingbot.connector.exchange.mexc.mexc_constants as CONSTANTS
from hummingbot.connector.exchange.mexc.mexc_user_stream_tracker import MexcUserStreamTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class MexcUserStreamTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = MexcAuth(api_key='testAPIKey',
                                  secret_key='testSecret', )
        self.tracker = MexcUserStreamTracker(throttler=throttler, mexc_auth=auth_assistant)

        self.mocking_assistant = NetworkMockingAssistant()
        self.ev_loop = asyncio.get_event_loop()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.tracker.start())
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value,
                                                             ujson.dumps({'channel': 'push.personal.order'}))

        first_received_message = self.async_run_with_timeout(self.tracker.user_stream.get())

        self.assertEqual({'channel': 'push.personal.order'}, first_received_message)
