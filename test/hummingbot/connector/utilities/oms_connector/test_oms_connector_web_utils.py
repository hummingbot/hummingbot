import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import build_api_factory
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse


class OMSConnectorWebUtilsTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ws_url = "ws://someUrl"

    def setUp(self) -> None:
        super().setUp()
        self.api_factory = build_api_factory()

    async def asyncSetUp(self) -> None:
        self.ws_assistant = await self.api_factory.get_ws_assistant()
        self.rest_assistant = await self.api_factory.get_rest_assistant()
        self.mocking_assistant = NetworkMockingAssistant()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_ws_pre_processor(self, ws_connect_mock: AsyncMock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        endpoint = "someEndpoint"
        msg_data = {"someAttribute": "someValue"}
        msg_payload = {
            "m": 0,
            "n": endpoint,
            "o": msg_data,
        }
        msg = WSJSONRequest(payload=msg_payload)
        await (self.ws_assistant.connect(ws_url=self.ws_url))
        await (self.ws_assistant.send(msg))

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(1, len(sent_messages))

        sent_msg = sent_messages[0]
        expected_payload = {
            "m": 0,
            "i": 2,
            "n": endpoint,
            "o": json.dumps(msg_data),
        }

        self.assertEqual(expected_payload, sent_msg)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_ws_post_processor(self, ws_connect_mock: AsyncMock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        msg_mock = {
            "m": 1,
            "i": 2,
            "n": "someEndpoint",
            "o": json.dumps({"someAttribute": "someValue"}),
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(msg_mock),
        )

        await (self.ws_assistant.connect(ws_url=self.ws_url))
        resp: Optional[WSResponse] = await (self.ws_assistant.receive())

        self.assertIsNotNone(resp)

        data = resp.data
        expected_data = {
            "m": 1,
            "i": 2,
            "n": "someEndpoint",
            "o": {"someAttribute": "someValue"},
        }

        self.assertEqual(expected_data, data)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_ws_increments_msg_counter(self, ws_connect_mock: AsyncMock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        endpoint = "someEndpoint"
        msg_data = {"someAttribute": "someValue"}
        msg_payload = {
            "m": 0,
            "n": endpoint,
            "o": msg_data,
        }
        msg = WSJSONRequest(payload=msg_payload)
        await (self.ws_assistant.connect(ws_url=self.ws_url))
        await (self.ws_assistant.send(msg))
        await (self.ws_assistant.send(msg))

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_messages))

        first_sent_msg = sent_messages[0]
        first_expected_payload = {
            "m": 0,
            "i": 2,
            "n": endpoint,
            "o": json.dumps(msg_data),
        }

        self.assertEqual(first_expected_payload, first_sent_msg)

        second_sent_msg = sent_messages[1]
        second_expected_payload = {
            "m": 0,
            "i": 4,
            "n": endpoint,
            "o": json.dumps(msg_data),
        }

        self.assertEqual(second_expected_payload, second_sent_msg)
