import asyncio
import json
import unittest
from collections import Awaitable
from typing import Dict, List
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_api_user_stream_data_source import (
    CoinbaseProAPIUserStreamDataSource
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_utils import build_coinbase_pro_web_assistant_factory
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class TestCoinbaseProAPIUserStreamDataSource(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        auth = CoinbaseProAuth(api_key="SomeAPIKey", secret_key="shht", passphrase="SomePassPhrase")
        self.mocking_assistant = NetworkMockingAssistant()
        web_assistants_factory = build_coinbase_pro_web_assistant_factory(auth)
        self.data_source = CoinbaseProAPIUserStreamDataSource(
            trading_pairs=[self.trading_pair], web_assistants_factory=web_assistants_factory
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_ws_open_message_mock(self) -> Dict:
        message = {
            "type": "open",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": self.trading_pair,
            "sequence": 10,
            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
            "price": "200.2",
            "remaining_size": "1.00",
            "side": "sell"
        }
        return message

    def get_ws_match_message_mock(self) -> Dict:
        message = {
            "type": "match",
            "trade_id": 10,
            "sequence": 50,
            "maker_order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": self.trading_pair,
            "size": "5.23512",
            "price": "400.23",
            "side": "sell"
        }
        return message

    def get_ws_change_message_mock(self) -> Dict:
        message = {
            "type": "change",
            "time": "2014-11-07T08:19:27.028459Z",
            "sequence": 80,
            "order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
            "product_id": self.trading_pair,
            "new_size": "5.23512",
            "old_size": "12.234412",
            "price": "400.23",
            "side": "sell"
        }
        return message

    def get_ws_done_message_mock(self) -> Dict:
        message = {
            "type": "done",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": self.trading_pair,
            "sequence": 10,
            "price": "200.2",
            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
            "reason": "filled",
            "side": "sell",
            "remaining_size": "0"
        }
        return message

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_processes_open_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_open_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        content = output_queue.get_nowait()

        self.assertEqual(resp, content)  # shallow comparison is ok

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_processes_match_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_match_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        content = output_queue.get_nowait()

        self.assertEqual(resp, content)  # shallow comparison is ok

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_processes_change_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_change_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        content = output_queue.get_nowait()

        self.assertEqual(resp, content)  # shallow comparison is ok

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_processes_done_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_done_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        content = output_queue.get_nowait()

        self.assertEqual(resp, content)  # shallow comparison is ok

    @patch(
        "hummingbot.connector.exchange.coinbase_pro"
        ".coinbase_pro_api_user_stream_data_source.CoinbaseProAPIUserStreamDataSource._sleep"
    )
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_raises_on_no_type(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(log_level="NETWORK", message="Unexpected error with WebSocket connection.")
        )
        self.assertTrue(output_queue.empty())

    @patch(
        "hummingbot.connector.exchange.coinbase_pro"
        ".coinbase_pro_api_user_stream_data_source.CoinbaseProAPIUserStreamDataSource._sleep"
    )
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_raises_on_error_message(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"type": "error", "message": "some error"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(log_level="NETWORK", message="Unexpected error with WebSocket connection.")
        )
        self.assertTrue(output_queue.empty())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_ignores_irrelevant_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps({"type": "received"})
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps({"type": "activate"})
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps({"type": "subscriptions"})
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())
