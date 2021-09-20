import asyncio
import json
import time
import unittest
from collections import Awaitable
from unittest.mock import patch, AsyncMock

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
    def test_on_message_skips_subscribe_unsubscribe_messages(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.ws.connect())
        async_iter = self.ws.on_message()

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps({"event": "subscribe"})
        )
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.async_run_with_timeout(async_iter.__anext__(), timeout=0.1)

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps({"event": "unsubscribe"})
        )
        self.async_run_with_timeout(self.ws.connect())
        async_iter = self.ws.on_message()
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.async_run_with_timeout(async_iter.__anext__(), timeout=0.1)
