import aiohttp
import asyncio
import json

from unittest import TestCase
from unittest.mock import patch
from typing import Dict, Any, Awaitable
from aioresponses import aioresponses

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
        self.tracker = AscendExUserStreamTracker(
            ascend_ex_auth=AscendExAuth(api_key="testAPIKey", secret_key="testSecret"),
            shared_client=self.session,
            throttler=self.throttler,
        )

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
        request = {"op": "auth", "args": ["testAPIKey", "testExpires", "testSignature"]}
        message = {"success": authenticated, "ret_msg": "", "conn_id": "testConnectionID", "request": request}

        return message

    @aioresponses()
    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_user_stream_authenticates_and_subscribes_to_events(self, api_mock, ws_connect_mock):
        output_queue = asyncio.Queue()
        self.ev_loop.create_task(self.tracker.data_source.listen_for_user_stream(self.ev_loop, output_queue))

        # Add the account group response
        resp = self._accountgroup_response()
        api_mock.get(f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}", body=json.dumps(resp))

        # Create WS mock
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Add the authentication response for the websocket
        resp = self._authentication_response(authenticated=True)
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(resp))
        # Add a dummy message for the websocket to read and include in the "messages" queue
        resp = {"data": "dummyMessage"}
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(resp))
        ret = self.ev_loop.run_until_complete(output_queue.get())

        self.assertEqual(
            {
                "success": True,
                "ret_msg": "",
                "conn_id": "testConnectionID",
                "request": {"op": "auth", "args": ["testAPIKey", "testExpires", "testSignature"]},
            },
            ret,
        )

        ret = self.ev_loop.run_until_complete(output_queue.get())

        self.assertEqual(resp, ret)

    @aioresponses()
    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_user_stream_authenticates_and_handles_ping_message(self, api_mock, ws_connect_mock):
        output_queue = asyncio.Queue()
        self.ev_loop.create_task(self.tracker.data_source.listen_for_user_stream(self.ev_loop, output_queue))

        # Add the account group response
        resp = self._accountgroup_response()
        api_mock.get(f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}", body=json.dumps(resp))

        # Create WS mock
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Add the authentication response for the websocket
        resp = self._authentication_response(authenticated=True)
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(resp))
        self.ev_loop.run_until_complete(output_queue.get())

        resp = {"m": "ping", "hp": 3}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(resp),
            message_type=aiohttp.WSMsgType.TEXT,
        )

        # Add a dummy message for the websocket to read and include in the "messages" queue
        resp = {"data": "dummyMessage"}
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(resp))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_json = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertTrue(any(["pong" in str(payload) for payload in sent_json]))
