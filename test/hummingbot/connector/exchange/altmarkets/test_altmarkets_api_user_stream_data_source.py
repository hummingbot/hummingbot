import asyncio
import json
import time
import unittest
from typing import Awaitable, Dict
from unittest.mock import AsyncMock, patch

import numpy as np

from hummingbot.connector.exchange.altmarkets.altmarkets_api_user_stream_data_source import (
    AltmarketsAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.altmarkets.altmarkets_auth import AltmarketsAuth
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestAltmarketsAPIUserStreamDataSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        altmarkets_auth = AltmarketsAuth(api_key="someKey", secret_key="someSecret")
        self.data_source = AltmarketsAPIUserStreamDataSource(AsyncThrottler(Constants.RATE_LIMITS), altmarkets_auth=altmarkets_auth, trading_pairs=[self.trading_pair])

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_user_trades_mock(self) -> Dict:
        user_trades = {
            "trade": {
                "amount": "1.0",
                "created_at": 1615978645,
                "id": 9618578,
                "market": "rogerbtc",
                "order_id": 2324774,
                "price": "0.00000004",
                "side": "sell",
                "taker_type": "sell",
                "total": "0.00000004"
            }
        }
        return user_trades

    def get_user_orders_mock(self) -> Dict:
        user_orders = {
            "order": {
                "id": 9401,
                "market": "rogerbtc",
                "kind": "ask",
                "side": "sell",
                "ord_type": "limit",
                "price": "0.00000099",
                "avg_price": "0.00000099",
                "state": "wait",
                "origin_volume": "7000.0",
                "remaining_volume": "2810.1",
                "executed_volume": "4189.9",
                "at": 1596481983,
                "created_at": 1596481983,
                "updated_at": 1596553643,
                "trades_count": 272
            }
        }
        return user_orders

    def get_user_balance_mock(self) -> Dict:
        user_balance = {
            "balance": {
                "currency": self.base_asset,
                "balance": "1032951.325075926",
                "locked": "1022943.325075926",
            }
        }
        return user_balance

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_user_trades(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        output_queue = asyncio.Queue()
        self.ev_loop.create_task(self.data_source.listen_for_user_stream(output_queue))

        resp = self.get_user_trades_mock()
        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(resp))
        ret = self.async_run_with_timeout(coroutine=output_queue.get())
        self.assertEqual(ret, resp)

        resp = self.get_user_orders_mock()
        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(resp))
        ret = self.async_run_with_timeout(coroutine=output_queue.get())

        self.assertEqual(ret, resp)

        resp = self.get_user_balance_mock()
        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(resp))
        ret = self.async_run_with_timeout(coroutine=output_queue.get())

        self.assertEqual(ret, resp)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_skips_subscribe_unsubscribe_messages_updates_last_recv_time(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {
            "success": {
                "message": "subscribed",
                "time": 1632223851,
                "streams": "trade"
            }
        }
        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(resp))
        resp = {
            "success": {
                "message": "unsubscribed",
                "time": 1632223851,
                "streams": "trade"
            }
        }
        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(resp))

        output_queue = asyncio.Queue()
        self.ev_loop.create_task(self.data_source.listen_for_user_stream(output_queue))
        self.mocking_assistant.run_until_all_text_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())
        np.testing.assert_allclose([time.time()], self.data_source.last_recv_time, rtol=1)
