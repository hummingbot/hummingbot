import asyncio
import json
import time
import unittest
from collections import Awaitable
from unittest.mock import patch, AsyncMock

import aiohttp
import numpy as np

from hummingbot.connector.exchange.gate_io.gate_io_websocket import GateIoWebsocket
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class GateIoWebsocketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ev_loop = asyncio.get_event_loop()
        self.ws = GateIoWebsocket()
        self.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe(self, mock_ws):
        subscription_channel = "someChannel"
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.ws.connect())
        ret = self.async_run_with_timeout(self.ws.subscribe(channel=subscription_channel))

        np.testing.assert_allclose([time.time()], [ret], rtol=1)
        calls = self.mocking_assistant.json_messages_sent_through_websocket(mock_ws.return_value)
        self.assertEqual(1, len(calls))
        subscription_call = calls[0]
        self.assertEqual("subscribe", subscription_call["event"])
        self.assertEqual(ret, subscription_call["time"])
        self.assertEqual(subscription_channel, subscription_call["channel"])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_unsubscribe(self, mock_ws):
        subscription_channel = "someChannel"
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.ws.connect())
        ret = self.async_run_with_timeout(self.ws.unsubscribe(channel=subscription_channel))

        np.testing.assert_allclose([time.time()], [ret], rtol=1)
        calls = self.mocking_assistant.json_messages_sent_through_websocket(mock_ws.return_value)
        self.assertEqual(1, len(calls))
        subscription_call = calls[0]
        self.assertEqual("unsubscribe", subscription_call["event"])
        self.assertEqual(ret, subscription_call["time"])
        self.assertEqual(subscription_channel, subscription_call["channel"])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_on_message(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.ws.connect())
        async_iter = self.ws.on_message()

        mock_event = "somEvent"
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps({"event": mock_event})
        )

        ret = self.async_run_with_timeout(async_iter.__anext__(), timeout=0.1)

        self.assertEqual(mock_event, ret["event"])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ping_sent_ping_ignored(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.closed = False

        self.async_run_with_timeout(self.ws.connect())
        async_iter = self.ws.on_message()

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, message="", message_type=aiohttp.WSMsgType.PING  # should be ignored
        )
        mock_event = "somEvent"
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps({"event": mock_event})
        )

        ret = self.async_run_with_timeout(async_iter.__anext__(), timeout=1)

        mock_ws.return_value.pong.assert_called()
        self.assertEqual(mock_event, ret["event"])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_last_recv_time_set_on_pong(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.closed = False

        self.async_run_with_timeout(self.ws.connect())
        async_iter = self.ws.on_message()

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, message="", message_type=aiohttp.WSMsgType.PONG  # should be ignored
        )
        anext_task = self.ev_loop.create_task(async_iter.__anext__())

        try:
            self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)
            np.testing.assert_allclose([self.ws.last_recv_time], [time.time()], rtol=1)
        except Exception:
            raise
        finally:
            anext_task.cancel()

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_backup_ping_pong(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.closed = False
        default_receive = mock_ws.return_value.receive.side_effect

        self.async_run_with_timeout(self.ws.connect())
        async_iter = self.ws.on_message()

        async def switch_back_and_raise_timeout(*args, **kwargs):
            mock_ws.return_value.receive.side_effect = default_receive
            raise asyncio.TimeoutError

        mock_ws.return_value.receive.side_effect = switch_back_and_raise_timeout
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps({"channel": "spot.pong"})  # should be ignored
        )
        mock_event = "somEvent"
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps({"event": mock_event})
        )

        ret = self.async_run_with_timeout(async_iter.__anext__(), timeout=1)

        self.assertEqual(mock_event, ret["event"])
