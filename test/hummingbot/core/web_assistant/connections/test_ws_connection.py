import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import List
from unittest.mock import AsyncMock, patch

import aiohttp
from aiohttp import WebSocketError

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class WSConnectionTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ws_url = "ws://some/url"
        cls.max_msg_size = 4194304

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        await self.mocking_assistant.async_init()
        self.client_session = aiohttp.ClientSession()
        self.ws_connection = WSConnection(self.client_session)
        self.async_tasks: List[asyncio.Task] = []

    async def asyncTearDown(self) -> None:
        await self.client_session.close()
        for task in self.async_tasks:
            task.cancel()
        await super().asyncTearDown()

    def tearDown(self) -> None:
        super().tearDown()

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connect_and_disconnect(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.assertFalse(self.ws_connection.connected)

        await self.ws_connection.connect(self.ws_url)

        self.assertTrue(self.ws_connection.connected)

        await self.ws_connection.disconnect()

        self.assertFalse(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_attempt_to_connect_second_time_raises(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)

        with self.assertRaises(RuntimeError) as e:
            await self.ws_connection.connect(self.ws_url)

        self.assertEqual("WS is connected.", str(e.exception))

    async def test_send_when_disconnected_raises(self):
        request = WSJSONRequest(payload={"one": 1})

        with self.assertRaises(RuntimeError) as e:
            await self.ws_connection.send(request)

        self.assertEqual("WS is not connected.", str(e.exception))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_send(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        request = WSJSONRequest(payload={"one": 1})

        await self.ws_connection.send(request)

        json_msgs = self.mocking_assistant.json_messages_sent_through_websocket(
            ws_connect_mock.return_value
        )

        self.assertEqual(1, len(json_msgs))
        self.assertEqual(request.payload, json_msgs[0])

    async def test_receive_when_disconnected_raises(self):
        with self.assertRaises(RuntimeError) as e:
            await self.ws_connection.receive()

        self.assertEqual("WS is not connected.", str(e.exception))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_raises_on_timeout(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        def raise_timeout(*_, **__):
            raise asyncio.TimeoutError

        ws_connect_mock.return_value.receive.side_effect = raise_timeout
        await self.ws_connection.connect(self.ws_url)

        with self.assertRaises(asyncio.TimeoutError) as e:
            await self.ws_connection.receive()

        self.assertEqual("Message receive timed out.", str(e.exception))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        data = {"one": 1}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(data)
        )

        self.assertEqual(0, self.ws_connection.last_recv_time)

        response = await self.ws_connection.receive()

        self.assertIsInstance(response, WSResponse)
        self.assertEqual(data, response.data)
        self.assertNotEqual(0, self.ws_connection.last_recv_time)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_disconnects_and_raises_on_aiohttp_closed(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.close_code = 1111
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSED
        )

        with self.assertRaises(ConnectionError) as e:
            await self.ws_connection.receive()

        self.assertEqual("The WS connection was closed unexpectedly. Close code = 1111 msg data: ", str(e.exception))
        self.assertFalse(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_disconnects_and_raises_on_aiohttp_close(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.close_code = 1111
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSE
        )

        with self.assertRaises(ConnectionError) as e:
            await self.ws_connection.receive()

        self.assertEqual("The WS connection was closed unexpectedly. Close code = 1111 msg data: ", str(e.exception))
        self.assertFalse(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_disconnects_and_raises_on_aiohttp_max_size(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url, self.max_msg_size)

        # Simulating the WebSocket closing with error code 1009 (message too big)
        ws_connect_mock.return_value.close_code = aiohttp.WSCloseCode.MESSAGE_TOO_BIG
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=WebSocketError(code=aiohttp.WSCloseCode.MESSAGE_TOO_BIG, message=""),
            message_type=aiohttp.WSMsgType.ERROR,
        )
        with self.assertRaises(WebSocketError) as e:
            await self.ws_connection.receive()

        # Validate the correct exception is raised with the appropriate message
        self.assertEqual(str(e.exception), "The WS message is too big: ")
        self.assertFalse(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_disconnects_and_raises_on_aiohttp_max_size_error(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.close_code = 1111
        await self.ws_connection.connect(self.ws_url, self.max_msg_size)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.ERROR,
        )

        with self.assertRaises(ConnectionError) as e:
            await self.ws_connection.receive()

        self.assertEqual("WS error: ", str(e.exception))
        self.assertFalse(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ignores_aiohttp_close_msg_if_disconnect_called(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSED
        )
        prev_side_effect = ws_connect_mock.return_value.receive.side_effect

        async def disconnect_on_side_effect(*args, **kwargs):
            await self.ws_connection.disconnect()
            return await prev_side_effect(*args, **kwargs)

        ws_connect_mock.return_value.receive.side_effect = disconnect_on_side_effect

        response = await self.ws_connection.receive()

        self.assertFalse(self.ws_connection.connected)
        self.assertIsNone(response)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ignores_ping(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PING
        )
        data = {"one": 1}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(data)
        )

        response = await self.ws_connection.receive()

        self.assertEqual(data, response.data)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_sends_pong_on_ping(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PING
        )
        receive_task = self.local_event_loop.create_task(self.ws_connection.receive())
        self.async_tasks.append(receive_task)

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        ws_connect_mock.return_value.pong.assert_called()

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ping_updates_last_recv_time(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PING
        )
        receive_task = self.local_event_loop.create_task(self.ws_connection.receive())
        self.async_tasks.append(receive_task)

        self.assertEqual(0, self.ws_connection.last_recv_time)

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertNotEqual(0, self.ws_connection.last_recv_time)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ignores_pong(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PONG
        )
        data = {"one": 1}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(data)
        )

        response = await self.ws_connection.receive()

        self.assertEqual(data, response.data)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_pong_updates_last_recv_time(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.ws_connection.connect(self.ws_url)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PONG
        )
        receive_task = self.local_event_loop.create_task(self.ws_connection.receive())
        self.async_tasks.append(receive_task)

        self.assertEqual(0, self.ws_connection.last_recv_time)

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertNotEqual(0, self.ws_connection.last_recv_time)
