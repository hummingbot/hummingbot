import asyncio
import json
import unittest
from collections import Awaitable
from typing import Optional
from unittest.mock import patch, AsyncMock

from aiohttp import WSMsgType

from hummingbot.connector.exchange.probit.probit_api_user_stream_data_source import (
    ProbitAPIUserStreamDataSource
)
from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.connector.exchange.probit import probit_constants as CONSTANTS
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class ProbitAPIUserStreamDataSourceTest(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.ev_loop = asyncio.get_event_loop()

        self.api_key = "someKey"
        self.api_secret = "someSecret"
        self.auth = ProbitAuth(self.api_key, self.api_secret)
        self.data_source = ProbitAPIUserStreamDataSource(
            self.auth, trading_pairs=[self.trading_pair]
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()

        self.async_task: Optional[asyncio.Task] = None

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def check_is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.probit.probit_auth.ProbitAuth.get_ws_auth_payload",
        new_callable=AsyncMock,
    )
    def test_listen_for_user_stream(self, get_ws_auth_payload_mock, ws_connect_mock):
        auth_msg = {
            "type": "authorization",
            "token": "someToken"
        }
        get_ws_auth_payload_mock.return_value = auth_msg

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value, message={"result": "ok"}  # authentication
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=json.dumps({"my_msg": "test"})  # first message
        )

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, output_queue)
        )

        self.mocking_assistant.run_until_all_json_messages_delivered(ws_connect_mock.return_value)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        sent_text_msgs = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(auth_msg, json.loads(sent_text_msgs[0]))

        sent_json_msgs = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        for sent_json_msg in sent_json_msgs:
            self.assertEqual("subscribe", sent_json_msg["type"])
            self.assertIn(sent_json_msg["channel"], CONSTANTS.WS_PRIVATE_CHANNELS)
            CONSTANTS.WS_PRIVATE_CHANNELS.remove(sent_json_msg["channel"])

        self.assertEqual(0, len(CONSTANTS.WS_PRIVATE_CHANNELS))
        self.assertNotEqual(0, self.data_source.last_recv_time)

    @patch("aiohttp.client.ClientSession.ws_connect")
    @patch(
        "hummingbot.connector.exchange.probit.probit_api_user_stream_data_source.ProbitAPIUserStreamDataSource._sleep",
        new_callable=AsyncMock,
    )
    def test_listen_for_user_stream_attempts_again_on_exception(self, sleep_mock, ws_connect_mock):
        called_event = asyncio.Event()

        async def _sleep(delay):
            called_event.set()
            await asyncio.sleep(delay)

        sleep_mock.side_effect = _sleep

        ws_connect_mock.side_effect = Exception
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, asyncio.Queue())
        )

        self.async_run_with_timeout(called_event.wait())

        self.check_is_logged(
            log_level="ERROR",
            message="Unexpected error with Probit WebSocket connection. Retrying after 30 seconds...",
        )

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_user_stream_stops_on_asyncio_cancelled_error(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_user_stream(self.ev_loop, asyncio.Queue())
            )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.probit.probit_auth.ProbitAuth.get_ws_auth_payload",
        new_callable=AsyncMock,
    )
    def test_listen_for_user_stream_registers_ping_msg(self, get_ws_auth_payload_mock, ws_connect_mock):
        auth_msg = {
            "type": "authorization",
            "token": "someToken"
        }
        get_ws_auth_payload_mock.return_value = auth_msg

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value, message={"result": "ok"}  # authentication
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=WSMsgType.PING
        )
        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, output_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())
        ws_connect_mock.return_value.pong.assert_called()
