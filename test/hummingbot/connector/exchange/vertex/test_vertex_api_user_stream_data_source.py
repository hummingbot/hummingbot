import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.vertex import vertex_constants as CONSTANTS, vertex_web_utils as web_utils
from hummingbot.connector.exchange.vertex.vertex_api_user_stream_data_source import VertexAPIUserStreamDataSource
from hummingbot.connector.exchange.vertex.vertex_auth import VertexAuth
from hummingbot.connector.exchange.vertex.vertex_exchange import VertexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestVertexAPIUserStreamDataSource(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "wBTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.TESTNET_DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        # NOTE: RANDOM KEYS GENERATED JUST FOR UNIT TESTS
        self.auth = VertexAuth(
            "0x2162Db26939B9EAF0C5404217774d166056d31B5",  # noqa: mock
            "5500eb16bf3692840e04fb6a63547b9a80b75d9cbb36b43ca5662127d4c19c83",  # noqa: mock
        )
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = VertexExchange(
            client_config_map,
            "0x2162Db26939B9EAF0C5404217774d166056d31B5",  # noqa: mock
            "5500eb16bf3692840e04fb6a63547b9a80b75d9cbb36b43ca5662127d4c19c83",  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        self.connector._exchange_market_info = {self.domain: self.get_exchange_market_info_mock()}

        self.api_factory = web_utils.build_api_factory(throttler=self.throttler, auth=self.auth)

        self.data_source = VertexAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            domain=self.domain,
            api_factory=self.api_factory,
            throttler=self.throttler,
            connector=self.connector,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def get_exchange_market_info_mock(self) -> Dict:
        exchange_rules = {
            1: {
                "product_id": 1,
                "oracle_price_x18": "26377830075239748635916",
                "risk": {
                    "long_weight_initial_x18": "900000000000000000",
                    "short_weight_initial_x18": "1100000000000000000",
                    "long_weight_maintenance_x18": "950000000000000000",
                    "short_weight_maintenance_x18": "1050000000000000000",
                    "large_position_penalty_x18": "0",
                },
                "config": {
                    "token": "0x5cc7c91690b2cbaee19a513473d73403e13fb431",  # noqa: mock
                    "interest_inflection_util_x18": "800000000000000000",
                    "interest_floor_x18": "10000000000000000",
                    "interest_small_cap_x18": "40000000000000000",
                    "interest_large_cap_x18": "1000000000000000000",
                },
                "state": {
                    "cumulative_deposits_multiplier_x18": "1001494499342736176",
                    "cumulative_borrows_multiplier_x18": "1005427534505418441",
                    "total_deposits_normalized": "336222763183987406404281",
                    "total_borrows_normalized": "106663044719707335242158",
                },
                "lp_state": {
                    "supply": "62619418496845923388438072",
                    "quote": {
                        "amount": "91404440604308224485238211",
                        "last_cumulative_multiplier_x18": "1000000008185212765",
                    },
                    "base": {
                        "amount": "3531841597039580133389",
                        "last_cumulative_multiplier_x18": "1001494499342736176",
                    },
                },
                "book_info": {
                    "size_increment": "1000000000000000",
                    "price_increment_x18": "1000000000000000000",
                    "min_size": "10000000000000000",
                    "collected_fees": "56936143536016463686263",
                    "lp_spread_x18": "3000000000000000",
                },
                "symbol": "wBTC",
                "market": "wBTC/USDC",
                "contract": "0x939b0915f9c3b657b9e9a095269a0078dd587491",  # noqa: mock
            },
        }
        return exchange_rules

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_unknown_event(self, mock_ws):
        unknown_event = [{"type": "unknown_event"}]
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(unknown_event))

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("hummingbot.connector.exchange.vertex.vertex_auth.VertexAuth._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_failure_logs_error(self, ws_connect_mock, auth_time_mock):
        auth_time_mock.side_effect = [100]
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        unknown_event = {"type": "unknown_event"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(unknown_event)
        )

        output_queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_subscription_messages))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_iter_message_throws_exception(self, sleep_mock, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.vertex.vertex_api_user_stream_data_source.VertexAPIUserStreamDataSource" "._time"
    )
    async def test_listen_for_user_stream_subscribe_message(self, time_mock, ws_connect_mock):
        time_mock.side_effect = [1000, 1100, 1101, 1102]  # Simulate first ping interval is already due

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps({})
        )

        output_queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        expected_message = {
            "id": 1,
            "method": "subscribe",
            "stream": {
                "product_id": 1,
                "subaccount": "0x2162Db26939B9EAF0C5404217774d166056d31B5",
                "type": "fill",
            },  # noqa: mock
        }
        self.assertEqual(expected_message, sent_messages[-2])

    # TODO: Need to assert that we send a ws.ping() frame on 30 s...
