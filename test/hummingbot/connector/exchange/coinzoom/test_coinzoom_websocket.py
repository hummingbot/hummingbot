import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants
from hummingbot.connector.exchange.coinzoom.coinzoom_websocket import CoinzoomWebsocket
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class CoinzoomWebsocketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_send_subscription_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        throttler = AsyncThrottler(Constants.RATE_LIMITS)
        websocket = CoinzoomWebsocket(throttler=throttler)
        message = {Constants.WS_SUB["TRADES"]: {'symbol': "BTC/USDT"}}

        self.async_run_with_timeout(websocket.connect())
        self.async_run_with_timeout(websocket.subscribe(message))
        self.async_run_with_timeout(websocket.unsubscribe(message))

        sent_requests = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)
        sent_subscribe_message = json.loads(sent_requests[0])
        expected_subscribe_message = {"TradeSummaryRequest": {"action": "subscribe", "symbol": "BTC/USDT"}}
        self.assertEquals(expected_subscribe_message, sent_subscribe_message)
        sent_unsubscribe_message = json.loads(sent_requests[0])
        expected_unsubscribe_message = {"TradeSummaryRequest": {"action": "subscribe", "symbol": "BTC/USDT"}}
        self.assertEquals(expected_unsubscribe_message, sent_unsubscribe_message)
