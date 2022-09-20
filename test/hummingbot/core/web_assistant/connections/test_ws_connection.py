import asyncio
import json
import unittest
from typing import Awaitable, List
from unittest.mock import AsyncMock, patch

import aiohttp

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection

test_events = []


class WSConnectionTest(unittest.IsolatedAsyncioTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.ws_url = "ws://some/url"
        test_events.append("setUpClass")

    def setUp(self) -> None:
        self.mocking_assistant = NetworkMockingAssistant()
        self.async_tasks: List[asyncio.Task] = []

        self.log_records = []
        test_events.append("setUp")

    async def asyncSetUp(self) -> None:
        self.mocking_assistant = NetworkMockingAssistant()
        self.async_tasks: List[asyncio.Task] = []
        self.client_session = aiohttp.ClientSession()
        self.ws_connection = WSConnection(self.client_session)
        self.data_feed = self.ws_connection
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        test_events.append("asyncSetUp")

    async def asyncTearDown(self) -> None:
        # This should not be needed: await self.ws_connection.disconnect()
        # This should not be needed: await self.client_session.close()
        for task in self.async_tasks:
            task.cancel()
        test_events.append("asyncSetUp")

    def tearDown(self) -> None:
        test_events.append("tearDown")

    async def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = await asyncio.wait_for(coroutine, timeout)
        return ret

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connect_and_disconnect(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.assertFalse(self.ws_connection.connected)

        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))

        self.assertTrue(self.ws_connection.connected)

        await self.async_run_with_timeout(self.ws_connection.disconnect())

        self.assertFalse(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_attempt_to_connect_second_time_raises(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))

        with self.assertRaises(RuntimeError) as e:
            await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))

        self.assertEqual("WS is connected.", str(e.exception))

    async def test_send_when_disconnected_raises(self):
        request = WSJSONRequest(payload={"one": 1})

        with self.assertRaises(RuntimeError) as e:
            await self.async_run_with_timeout(self.ws_connection.send(request))

        self.assertEqual("WS is not connected.", str(e.exception))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_send(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        request = WSJSONRequest(payload={"one": 1})

        await self.async_run_with_timeout(self.ws_connection.send(request))

        json_msgs = self.mocking_assistant.json_messages_sent_through_websocket(
            ws_connect_mock.return_value
        )

        self.assertEqual(1, len(json_msgs))
        self.assertEqual(request.payload, json_msgs[0])

    async def test_receive_when_disconnected_raises(self):
        with self.assertRaises(RuntimeError) as e:
            await self.async_run_with_timeout(self.ws_connection.receive())

        self.assertEqual("WS is not connected.", str(e.exception))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_calls_ping_on_timeout(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))

        ws_connect_mock.return_value.receive.side_effect = [
            asyncio.TimeoutError,
            aiohttp.WSMessage(type=aiohttp.WSMsgType.PONG, data="", extra=None),
            aiohttp.WSMessage(type=aiohttp.WSMsgType.TEXT, data=json.dumps({"one": 1}), extra=None)]
        ws_connect_mock.return_value.ping = AsyncMock()

        response = await self.async_run_with_timeout(self.ws_connection.receive())

        ws_connect_mock.return_value.ping.assert_called_once()
        self.assertIsInstance(response, WSResponse)
        self.assertEqual({"one": 1}, response.data)
        self.assertNotEqual(0, self.ws_connection.last_recv_time)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        data = {"one": 1}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(data)
        )

        self.assertEqual(0, self.ws_connection.last_recv_time)

        response = await self.async_run_with_timeout(self.ws_connection.receive())

        self.assertIsInstance(response, WSResponse)
        self.assertEqual(data, response.data)
        self.assertNotEqual(0, self.ws_connection.last_recv_time)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_disconnects_and_attempts_to_reconnect_on_aiohttp_closed(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.close_code = 1111
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))

        # First message is CLOSE
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSED
        )

        # Assuming connection re-established and TEXT arrives next
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.TEXT
        )

        await self.async_run_with_timeout(self.ws_connection.receive())

        # The connection error is logged
        close_msg = "The WS connection was closed unexpectedly, attempting to reconnect. Close code = 1111 msg data: "
        self.assertTrue(self.is_logged(log_level="WARNING", message=close_msg))

        # The connection is re-established
        self.assertTrue(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_disconnects_and_attempts_to_reconnect_on_aiohttp_close(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.close_code = 1111
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))

        # First message is CLOSE
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSE
        )

        # Assuming connection re-established and TEXT arrives next
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.TEXT
        )

        await self.async_run_with_timeout(self.ws_connection.receive())

        # The connection error is logged
        close_msg = "The WS connection was closed unexpectedly, attempting to reconnect. Close code = 1111 msg data: "
        self.assertTrue(self.is_logged(log_level="WARNING", message=close_msg))

        # The connection is re-established
        self.assertTrue(self.ws_connection.connected)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ignores_aiohttp_close_msg_if_disconnect_called(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.CLOSED
        )
        prev_side_effect = ws_connect_mock.return_value.receive.side_effect

        async def disconnect_on_side_effect(*args, **kwargs):
            await self.ws_connection.disconnect()
            return await prev_side_effect(*args, **kwargs)

        ws_connect_mock.return_value.receive.side_effect = disconnect_on_side_effect

        response = await self.async_run_with_timeout(self.ws_connection.receive())

        self.assertFalse(self.ws_connection.connected)
        self.assertIsNone(response)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ignores_ping(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PING
        )
        data = {"one": 1}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(data)
        )

        response = await self.async_run_with_timeout(self.ws_connection.receive())

        self.assertEqual(data, response.data)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_sends_pong_on_ping(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PING
        )
        receive_task = asyncio.create_task(self.ws_connection.receive())
        self.async_tasks.append(receive_task)

        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 1)

        ws_connect_mock.return_value.pong.assert_called()

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ping_updates_last_recv_time(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PING
        )
        receive_task = asyncio.create_task(self.ws_connection.receive())
        self.async_tasks.append(receive_task)

        self.assertEqual(0, self.ws_connection.last_recv_time)

        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 1)
        self.assertNotEqual(0, self.ws_connection.last_recv_time)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_ignores_pong(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PONG
        )
        data = {"one": 1}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps(data)
        )

        response = await self.async_run_with_timeout(self.ws_connection.receive())

        self.assertEqual(data, response.data)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_receive_pong_updates_last_recv_time(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        await self.async_run_with_timeout(self.ws_connection.connect(self.ws_url))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=aiohttp.WSMsgType.PONG
        )
        receive_task = asyncio.create_task(self.ws_connection.receive())
        self.async_tasks.append(receive_task)

        self.assertEqual(0, self.ws_connection.last_recv_time)

        # self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        all_delivered = self.mocking_assistant._all_incoming_websocket_aiohttp_delivered_event[
            ws_connect_mock.return_value]
        await asyncio.wait_for(all_delivered.wait(), 1)

        self.assertNotEqual(0, self.ws_connection.last_recv_time)
