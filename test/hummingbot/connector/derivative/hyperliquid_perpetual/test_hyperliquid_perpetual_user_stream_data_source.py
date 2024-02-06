import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.hyperliquid_perpetual import hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import HyperliquidPerpetualAuth
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
    HyperliquidPerpetualDerivative,
)
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_user_stream_data_source import (
    HyperliquidPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestHyperliquidPerpetualAPIUserStreamDataSource(unittest.TestCase):
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
        cls.use_vault = False
        cls.api_secret_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = HyperliquidPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret_key,
            use_vault=self.use_vault)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = HyperliquidPerpetualDerivative(
            client_config_map=client_config_map,
            hyperliquid_perpetual_api_key=self.api_key,
            hyperliquid_perpetual_api_secret=self.api_secret_key,
            use_vault=self.use_vault,
            trading_pairs=[])
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = HyperliquidPerpetualUserStreamDataSource(
            self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 2):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    async def get_token(self):
        return "be4ffcc9-2b2b-4c3e-9d47-68bf062cf651"

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_orders = {'channel': 'orderUpdates', 'data': [{'order': {'coin': 'ETH', 'side': 'A',
                                                                                  'limitPx': '2112.8', 'sz': '0.01',
                                                                                  'oid': 2260108845,
                                                                                  'timestamp': 1700688451563,
                                                                                  'origSz': '0.01',
                                                                                  'cloid': '0x48424f54534548554436306163343632'}, # noqa: mock
                                                                        'status': 'canceled',
                                                                        'statusTimestamp': 1700688453173}]}
        result_subscribe_trades = {'channel': 'user', 'data': {'fills': [
            {'coin': 'ETH', 'px': '2091.3', 'sz': '0.01', 'side': 'B', 'time': 1700688460805, 'startPosition': '0.0',
             'dir': 'Open Long', 'closedPnl': '0.0',
             'hash': '0x544c46b72e0efdada8cd04080bb32b010d005a7d0554c10c4d0287e9a2c237e7', 'oid': 2260113568, # noqa: mock
             # noqa: mock
             'crossed': True, 'fee': '0.005228', 'liquidationMarkPx': None}]}}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_orders_subscription = {
            "method": "subscribe",
            "subscription": {
                "type": "orderUpdates",
                "user": self.api_key,
            }
        }
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[0])
        expected_trades_subscription = {
            "method": "subscribe",
            "subscription": {
                "type": "user",
                "user": self.api_key,
            }
        }
        self.assertEqual(expected_trades_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private order and trades changes channels..."
        ))

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

    # @unittest.skip("Test with error")
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
