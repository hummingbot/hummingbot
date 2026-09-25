import asyncio
import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.lambdaplex import lambdaplex_constants as CONSTANTS
from hummingbot.connector.exchange.lambdaplex.lambdaplex_api_user_stream_data_source import (
    LambdaplexAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.lambdaplex.lambdaplex_auth import LambdaplexAuth
from hummingbot.connector.exchange.lambdaplex.lambdaplex_exchange import LambdaplexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


class LambdaplexUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.api_key = "testApiKey"
        cls.private_key = "MC4CAQAwBQYDK2VwBCIEIJETIXjnIFeh11KAJZVv45sLhH8gCrWbL902cBfzCHE3"  # noqa: invalidated
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base_asset, quote=cls.quote_asset)
        cls.exchange_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1234567890.000
        self.auth = LambdaplexAuth(
            api_key=self.api_key,
            private_key=self.private_key,
            time_provider=self.mock_time_provider,
        )
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        self.connector = LambdaplexExchange(
            lambdaplex_api_key=self.api_key,
            lambdaplex_private_key=self.private_key,
            trading_pairs=[],
            trading_required=False,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = LambdaplexAPIUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.exchange_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )

    @staticmethod
    def _get_successful_request_response(request_id: int) -> Dict[str, Any]:
        return {
            "id": str(request_id),
            "result": None,
            "status": "200"
        }

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_canceled_when_cancel_exception_during_initialization(self, mock_ws: AsyncMock):
        messages: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(messages)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_canceled_when_cancel_exception_during_authentication(self, mock_ws: AsyncMock):
        messages: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(messages)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_raises_cancel_exception(self, mock_ws: AsyncMock):
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_logs_authentication_failure(self, mock_api, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        error_mock_response = {
            "id": 1,
            "status": 401,
            "error": {"msg": "Invalid signature"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(error_mock_response),
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_login_message: Dict[str, Any] = {
            "id": 1,
            "method": CONSTANTS.WS_SESSION_LOGON_METHOD,
            "params": {
                "apiKey": self.api_key,
                "recvWindow": 5000,
                "signature": "t0JWo+U6NFKJZFt4j9IMbJ3soTZvrWbqrgNFAKp5ASY4RIgjaza8IsYJOCJgvtvCXTn3FIkKC2wyH7m0U3L3CQ==",
                "timestamp": 1234567890000,
            }
        }

        self.assertEqual(expected_login_message, sent_messages[0])
        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Error authenticating the private websocket connection. Response message {error_mock_response}"
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_authenticates(self, mock_api, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._get_successful_request_response(request_id=1))
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_login_message: Dict[str, Any] = {
            "id": 1,
            "method": CONSTANTS.WS_SESSION_LOGON_METHOD,
            "params": {
                "apiKey": self.api_key,
                "recvWindow": 5000,
                "signature": "t0JWo+U6NFKJZFt4j9IMbJ3soTZvrWbqrgNFAKp5ASY4RIgjaza8IsYJOCJgvtvCXTn3FIkKC2wyH7m0U3L3CQ==",
                "timestamp": 1234567890000,
            }
        }

        self.assertEqual(expected_login_message, sent_messages[0])
        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged(
                "INFO",
                "Lambdaplex private WebSocket connection successfully authenticated.",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_logs_private_stream_subscription_failure(self, mock_api, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._get_successful_request_response(request_id=1))
        )
        error_mock_response = {
            "id": 2,
            "status": 400,
            "error": {"msg": "Some error"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(error_mock_response),
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_subscription_message: Dict[str, Any] = {
            "id": 2,
            "method": CONSTANTS.WS_SESSION_SUBSCRIBE_METHOD,
        }

        self.assertEqual(expected_subscription_message, sent_messages[1])
        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Error subscribing to the private websocket stream. Response message {error_mock_response}"
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_subscribes_to_private_stream(self, mock_ws: AsyncMock):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._get_successful_request_response(request_id=1))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self._get_successful_request_response(request_id=2))
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        expected_subscription_message: Dict[str, Any] = {
            "id": 2,
            "method": CONSTANTS.WS_SESSION_SUBSCRIBE_METHOD,
        }

        self.assertEqual(2, len(sent_messages))
        self.assertEqual(expected_subscription_message, sent_messages[1])
        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged(
                "INFO",
                "Lambdaplex private WebSocket connection successfully authenticated.",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_queues_order_event(self, mock_ws: AsyncMock) -> None:
        client_order_id = "11"
        expected_exchange_order_id = "0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6"  # noqa: mock

        self.connector.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            price=Decimal("1000"),
            amount=Decimal("1"),
            initial_state=OrderState.OPEN,
        )
        expected_order_event: Dict[str, Any] = {
            "e": "orderUpdate",
            "E": 1499405658658,
            "s": self.exchange_trading_pair,
            "c": "mUvoqJxFIILMdfAW5iGSOW",
            "S": "BUY",
            "o": "LIMIT",
            "f": "GTC",
            "q": "1.00000000",
            "p": "1000",
            "P": "0.00000000",
            "C": "",
            "x": "ACCEPT",
            "X": "OPEN",
            "r": "NONE",
            "i": expected_exchange_order_id,  # noqa: mock
            "l": "0.00000000",
            "z": "0.00000000",
            "L": "0.00000000",
            "n": "0",
            "N": None,
            "T": 1499405658657,
            "t": -1,
            "I": "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
            "w": True,
            "m": True,
            "O": 1499405658657,
            "Z": "0.00000000",
            "Y": "0.00000000",
            "W": 1499405658657,
        }

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value, message=json.dumps(self._get_successful_request_response(request_id=1))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value, message=json.dumps(self._get_successful_request_response(request_id=2))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(websocket_mock=mock_ws.return_value, message=json.dumps(expected_order_event))

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(1, msg_queue.qsize())
        order_event_message = msg_queue.get_nowait()
        self.assertEqual(expected_order_event, order_event_message)
