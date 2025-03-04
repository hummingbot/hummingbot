from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, PropertyMock, patch

import aiohttp

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest, WSRequest, WSResponse
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class WSAssistantTest(IsolatedAsyncioWrapperTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await ConnectionsFactory().close()
        self.mocking_assistant = NetworkMockingAssistant()
        self.aiohttp_client_session = aiohttp.ClientSession()
        self.ws_connection = WSConnection(self.aiohttp_client_session)
        self.ws_assistant = WSAssistant(self.ws_connection)

    async def asyncTearDown(self) -> None:
        await self.aiohttp_client_session.close()
        await super().asyncTearDown()

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.connect")
    async def test_connect(self, connect_mock):
        ws_url = "ws://some.url"
        ping_timeout = 10
        message_timeout = 20
        max_msg_size = 4 * 1024 * 1024

        await self.ws_assistant.connect(ws_url, ping_timeout=ping_timeout, message_timeout=message_timeout, max_msg_size=max_msg_size)

        connect_mock.assert_called_with(ws_url=ws_url,
                                        ws_headers={},
                                        ping_timeout=ping_timeout,
                                        message_timeout=message_timeout,
                                        max_msg_size=max_msg_size)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.disconnect")
    async def test_disconnect(self, disconnect_mock):
        await (self.ws_assistant.disconnect())

        disconnect_mock.assert_called()

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    async def test_send(self, send_mock):
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        request = WSJSONRequest(payload)

        await (self.ws_assistant.send(request))

        self.assertEqual(1, len(sent_requests))

        sent_request = sent_requests[0]

        self.assertNotEqual(id(request), id(sent_request))  # has been cloned
        self.assertEqual(request, sent_request)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    async def test_send_pre_processes(self, send_mock):
        class SomePreProcessor(WSPreProcessorBase):
            async def pre_process(self, request_: RESTRequest) -> RESTRequest:
                request_.payload["two"] = 2
                return request_

        ws_assistant = WSAssistant(
            connection=self.ws_connection, ws_pre_processors=[SomePreProcessor()]
        )
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        request = WSJSONRequest(payload)

        await (ws_assistant.send(request))

        sent_request = sent_requests[0]
        expected = {"one": 1, "two": 2}

        self.assertEqual(expected, sent_request.payload)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    async def test_subscribe(self, send_mock):
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        request = WSJSONRequest(payload)

        await (self.ws_assistant.subscribe(request))

        self.assertEqual(1, len(sent_requests))

        sent_request = sent_requests[0]

        self.assertNotEqual(id(request), id(sent_request))  # has been cloned
        self.assertEqual(request, sent_request)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    async def test_ws_assistant_authenticates(self, send_mock):
        class Auth(AuthBase):
            async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
                pass

            async def ws_authenticate(self, request: WSRequest) -> WSRequest:
                request.payload["authenticated"] = True
                return request

        ws_assistant = WSAssistant(connection=self.ws_connection, auth=Auth())
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        req = WSJSONRequest(payload)
        auth_req = WSJSONRequest(payload, is_auth_required=True)

        await (ws_assistant.send(req))
        await (ws_assistant.send(auth_req))

        sent_request = sent_requests[0]
        auth_sent_request = sent_requests[1]
        expected = {"one": 1}
        auth_expected = {"one": 1, "authenticated": True}

        self.assertEqual(expected, sent_request.payload)
        self.assertEqual(auth_expected, auth_sent_request.payload)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.receive")
    async def test_receive(self, receive_mock):
        data = {"one": 1}
        response_mock = WSResponse(data)
        receive_mock.return_value = response_mock

        response = await (self.ws_assistant.receive())

        self.assertEqual(data, response.data)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_plain_text(self, ws_connect_mock):
        data = "pong"
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=data)
        await (self.ws_assistant.connect(ws_url="test.url"))
        response = await (self.ws_assistant.receive())

        self.assertEqual(data, response.data)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.receive")
    async def test_receive_post_processes(self, receive_mock):
        class SomePostProcessor(WSPostProcessorBase):
            async def post_process(self, response_: WSResponse) -> WSResponse:
                response_.data["two"] = 2
                return response_

        ws_assistant = WSAssistant(
            connection=self.ws_connection, ws_post_processors=[SomePostProcessor()]
        )
        data = {"one": 1}
        response_mock = WSResponse(data)
        receive_mock.return_value = response_mock

        response = await (ws_assistant.receive())

        expected = {"one": 1, "two": 2}

        self.assertEqual(expected, response.data)

    @patch(
        "hummingbot.core.web_assistant.connections.ws_connection.WSConnection.connected",
        new_callable=PropertyMock,
    )
    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.receive")
    async def test_iter_messages(self, receive_mock, connected_mock):
        connected_mock.return_value = True
        data = {"one": 1}
        response_mock = WSResponse(data)
        receive_mock.return_value = response_mock
        iter_messages_iterator = self.ws_assistant.iter_messages()

        response = await (iter_messages_iterator.__anext__())

        self.assertEqual(data, response.data)

        connected_mock.return_value = False

        with self.assertRaises(StopAsyncIteration):
            await (iter_messages_iterator.__anext__())
