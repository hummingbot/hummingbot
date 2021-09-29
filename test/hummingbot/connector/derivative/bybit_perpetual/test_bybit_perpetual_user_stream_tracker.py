import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from typing import Optional

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_user_stream_tracker import BybitPerpetualUserStreamTracker


class BybitPerpetualUserStreamTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        self.tracker = BybitPerpetualUserStreamTracker(auth_assistant=BybitPerpetualAuth(api_key='testAPIKey', secret_key='testSecret'))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    async def _get_next_received_message(self, timeout: Optional[int] = None):
        return await self.ws_incoming_messages.get()

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.receive_json.side_effect = self._get_next_received_message
        return ws

    def _authentication_response(self, authenticated: bool) -> str:
        request = {"op": "auth",
                   "args": ['testAPIKey', 'testExpires', 'testSignature']}
        message = {"success": authenticated,
                   "ret_msg": "",
                   "conn_id": "testConnectionID",
                   "request": request}

        return message

    def _add_successful_authentication_response(self):
        self.ws_incoming_messages.put_nowait(self._authentication_response(True))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self._create_ws_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.tracker.start())
        # Add the authentication response for the websocket
        self._add_successful_authentication_response()
        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.ws_incoming_messages.put_nowait('dummyMessage')

        first_received_message = asyncio.get_event_loop().run_until_complete(self.tracker.user_stream.get())

        self.assertEqual('dummyMessage', first_received_message)
