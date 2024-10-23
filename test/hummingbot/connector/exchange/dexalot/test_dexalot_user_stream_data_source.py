import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS
from hummingbot.connector.exchange.dexalot.dexalot_api_user_stream_data_source import DexalotAPIUserStreamDataSource
from hummingbot.connector.exchange.dexalot.dexalot_auth import DexalotAuth
from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestDexalotAPIUserStreamDataSource(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "AVAX"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = DexalotAuth(
            api_key=self.api_key,
            secret_key=self.api_secret_key,
            time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = DexalotExchange(
            client_config_map=client_config_map,
            dexalot_api_key=self.api_key,
            dexalot_api_secret=self.api_secret_key,
            trading_pairs=[self.trading_pair])
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = DexalotAPIUserStreamDataSource(
            self.auth,
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
    def test_listen_for_user_stream_subscribes_to_orders_and_trades_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_orders = {
            'data': {
                'version': 2, 'traderaddress': '0x335e5b9a72A3aBA693B68bDe44FeBA1252e54cFc',  # noqa: mock
                'pair': 'AVAX/USDC',
                'orderId': '0x000000000000000000000000000000000000000000000000000000006bff4383',  # noqa: mock
                'clientOrderId': '0xab79ca8d0140a5fd64c7e55aad74a329e8f04819486987a120e2c9a03b722556',  # noqa: mock
                'price': '26.0',
                'totalamount': '0.0', 'quantity': '1.0', 'side': 'SELL', 'sideId': 1, 'type1': 'LIMIT',
                'type1Id': 1,
                'type2': 'GTC', 'type2Id': 0, 'status': 'NEW', 'statusId': 0, 'quantityfilled': '0.0',
                'totalfee': '0.0',
                'code': '', 'blockTimestamp': 1725903204,
                'transactionHash': '0xbb86fc3ba6702b59febd14cebea8fdea89fded7058b2d226eb7b3c2e18507473',  # noqa: mock
                'blockNumber': 23252530,
                'blockHash': '0xb91986c528dc2dcf91d60072bc1f1694005ee0741c953de2ea3a5c908d5921bc'  # noqa: mock
            },
            'type': 'orderStatusUpdateEvent'
        }
        result_subscribe_trades = {
            'data': {
                'version': 1, 'pair': 'AVAX/USDC', 'price': '21.74', 'quantity': '1.0',
                'makerOrder': '0x000000000000000000000000000000000000000000000000000000006bd377e9',  # noqa: mock
                'takerOrder': '0x000000000000000000000000000000000000000000000000000000006bd37829',  # noqa: mock
                'feeMaker': '0.021',
                'feeTaker': '0.0', 'takerSide': 'BUY', 'execId': 1809020970,
                'addressMaker': '0x335e5b9a72A3aBA693B68bDe44FeBA1252e54cFc',  # noqa: mock
                'addressTaker': '0xa671DCd02e6e7f482B3Da15e9baAE1d049DB35eF',  # noqa: mock
                'blockNumber': 23064654,
                'blockTimestamp': 1725525869,
                'blockHash': '0x543a96fa717df709e1a08fc102b4628c1f3b5850b615f2f8dbcc037c27e2b019',  # noqa: mock
                'transactionHash': '0xe34b34f8153ca90fa289e0f5627efec649a84d27eb057b2d6560f663a180c69c',  # noqa: mock
                'takerSideId': 0
            },
            'type': 'executionEvent'
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

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription = "tradereventsubscribe"
        self.assertEqual(expected_subscription, sent_subscription_messages[0]["type"])
        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private order changes and trade updates channels..."
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
