import asyncio
import aiohttp
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from typing import Dict, Any, Awaitable
from aioresponses import aioresponses
import json

from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex.ascend_ex_user_stream_tracker import AscendExUserStreamTracker
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class AscendExUserStreamTrackerTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.mocking_assistant = NetworkMockingAssistant()
        self.listening_task = None
        self.session = None
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker = AscendExUserStreamTracker(ascend_ex_auth=AscendExAuth(api_key='testAPIKey', secret_key='testSecret'), shared_client=self.session, throttler=self.throttler)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _accountgroup_response(self) -> Dict[str, Any]:
        message = {"data": {"accountGroup": 12345679}}
        return message

    def _authentication_response(self, authenticated: bool) -> Dict[str, Any]:
        request = {"op": "auth",
                   "args": ['testAPIKey', 'testExpires', 'testSignature']}
        message = {"success": authenticated,
                   "ret_msg": "",
                   "conn_id": "testConnectionID",
                   "request": request}

        return message

    @aioresponses()
    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    async def do_authenticate_and_subscribe(self, api_mock, ws_connect_mock):
        self.tracker._shared_client = aiohttp.ClientSession()

        ret = {}

        output_queue = asyncio.Queue()
        self.ev_loop.create_task(self.tracker.data_source.listen_for_user_stream(self.ev_loop, output_queue))

        # Add the account group response
        resp = self._accountgroup_response()
        api_mock.get(f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}", body=json.dumps(resp))

        # Create WS mock
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Add the authentication response for the websocket
        resp = self._authentication_response(authenticated=True)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        ret["output_queue authentication"] = await output_queue.get()

        # Add a dummy message for the websocket to read and include in the "messages" queue
        resp = 'dummyMessage'
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        ret["output_queue first message"] = await output_queue.get()

        await self.tracker._shared_client.close()
        return ret

    def test_listening_process_authenticates_and_subscribes_to_events(self):
        ret = self.ev_loop.run_until_complete(self.do_authenticate_and_subscribe())
        self.assertEqual({'success': True, 'ret_msg': '', 'conn_id': 'testConnectionID', 'request': {'op': 'auth', 'args': ['testAPIKey', 'testExpires', 'testSignature']}}, ret["output_queue authentication"])
        self.assertEqual('dummyMessage', ret["output_queue first message"])
