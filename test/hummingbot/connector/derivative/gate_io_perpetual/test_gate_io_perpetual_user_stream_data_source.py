import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.gate_io_perpetual import gate_io_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_auth import GateIoPerpetualAuth
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_derivative import GateIoPerpetualDerivative
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_user_stream_data_source import (
    GateIoPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestGateIoPerpetualAPIUserStreamDataSource(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"
        cls.user_id = "someUserId"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = GateIoPerpetualAuth(
            api_key=self.api_key,
            secret_key=self.api_secret_key)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = GateIoPerpetualDerivative(
            client_config_map=client_config_map,
            gate_io_perpetual_api_key="",
            gate_io_perpetual_secret_key="",
            gate_io_perpetual_user_id="",
            trading_pairs=[])
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = GateIoPerpetualAPIUserStreamDataSource(
            self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            user_id=self.user_id,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_user_stream_data_source.GateIoPerpetualAPIUserStreamDataSource"
        "._time")
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, time_mock, ws_connect_mock):
        time_mock.return_value = 1000
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_orders = {
            "time": 1611541000,
            "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            "event": "subscribe",
            "error": None,
            "result": {
                "status": "success"
            }
        }
        result_subscribe_trades = {
            "time": 1611541000,
            "channel": CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            "event": "subscribe",
            "error": None,
            "result": {
                "status": "success"
            }
        }
        result_subscribe_positions = {
            "time": 1611541000,
            "channel": CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
            "event": "subscribe",
            "error": None,
            "result": {
                "status": "success"
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_positions))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_subscription_messages))
        expected_orders_subscription = {
            "time": int(self.mock_time_provider.time()),
            "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            "event": "subscribe",
            "payload": [self.user_id, self.ex_trading_pair],
            "auth": {
                "KEY": self.api_key,
                "SIGN": '0fb3b313fe07c7d23164a4ae86adf306a48f5787c54b9a7595f0a50a164c01eb54d8de5d5ad65fbc3ea94e60e73446d999d23424e52f715713ee6cb32a7d0df1',# noqa: mock
                "method": "api_key"},
        }
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[0])
        expected_trades_subscription = {
            "time": int(self.mock_time_provider.time()),
            "channel": CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            "event": "subscribe",
            "payload": [self.user_id, self.ex_trading_pair],
            "auth": {
                "KEY": self.api_key,
                "SIGN": 'a7681c836307cbb57c7ba7a66862120770c019955953e5ec043fd00e93722d478096f0a8238e3f893dcb3e0f084dc67a2a7ff6e6e08bc1bf0ad80fee57fff113',# noqa: mock
                "method": "api_key"}
        }
        self.assertEqual(expected_trades_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private order changes channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_user_stream_data_source.GateIoPerpetualAPIUserStreamDataSource"
        "._time")
    def test_listen_for_user_stream_skips_subscribe_unsubscribe_messages(self, time_mock, ws_connect_mock):
        time_mock.return_value = 1000
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_orders = {
            "time": 1611541000,
            "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            "event": "subscribe",
            "error": None,
            "result": {
                "status": "success"
            }
        }
        result_subscribe_trades = {
            "time": 1611541000,
            "channel": CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            "event": "subscribe",
            "error": None,
            "result": {
                "status": "success"
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_pong_payload(self, mock_ws):
        mock_pong = {
            "time": 1545404023,
            "channel": CONSTANTS.PONG_CHANNEL_NAME,
            "event": "",
            "error": None,
            "result": None
        }

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(mock_pong))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_iter_message_throws_exception(self, sleep_mock, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
