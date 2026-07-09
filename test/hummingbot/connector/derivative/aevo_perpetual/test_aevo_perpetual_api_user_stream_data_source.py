import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_user_stream_data_source import (
    AevoPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class AevoPerpetualAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-PERP"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None

        self._wallet_patcher = patch("eth_account.Account.from_key", return_value=MagicMock())
        self._wallet_patcher.start()

        self.auth = AevoPerpetualAuth(
            api_key="test-key",
            api_secret="test-secret",
            signing_key="0x1",
            account_address="0xabc",
            domain=self.domain,
        )
        self.connector = AevoPerpetualDerivative(
            aevo_perpetual_api_key="",
            aevo_perpetual_api_secret="",
            aevo_perpetual_signing_key="",
            aevo_perpetual_account_address="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = AevoPerpetualAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self._wallet_patcher.stop()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    async def test_last_recv_time_without_ws_assistant_returns_zero(self):
        self.assertEqual(0, self.data_source.last_recv_time)

    async def test_get_ws_assistant_returns_cached_instance(self):
        ws_mock = AsyncMock(spec=WSAssistant)
        self.data_source._api_factory.get_ws_assistant = AsyncMock(return_value=ws_mock)

        first = await self.data_source._get_ws_assistant()
        second = await self.data_source._get_ws_assistant()

        self.assertIs(ws_mock, first)
        self.assertIs(first, second)
        self.data_source._api_factory.get_ws_assistant.assert_awaited_once()

    async def test_authenticate_raises_on_error_response(self):
        ws_mock = AsyncMock(spec=WSAssistant)
        ws_mock.receive = AsyncMock(return_value=WSResponse(data={"error": "bad auth"}))

        with self.assertRaises(IOError):
            await self.data_source._authenticate(ws_mock)

    async def test_authenticate_sends_auth_request(self):
        ws_mock = AsyncMock(spec=WSAssistant)
        ws_mock.receive = AsyncMock(return_value=WSResponse(data={"result": "ok"}))

        await self.data_source._authenticate(ws_mock)

        sent_request = ws_mock.send.call_args.args[0]
        self.assertIsInstance(sent_request, WSJSONRequest)
        self.assertEqual(self.auth.get_ws_auth_payload(), sent_request.payload)

    @patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_user_stream_data_source.safe_ensure_future")
    async def test_connected_websocket_assistant_connects_and_starts_ping(self, safe_future_mock):
        ws_mock = AsyncMock(spec=WSAssistant)
        self.data_source._get_ws_assistant = AsyncMock(return_value=ws_mock)

        ws_assistant = await self.data_source._connected_websocket_assistant()

        self.assertIs(ws_mock, ws_assistant)
        ws_mock.connect.assert_awaited_once_with(
            ws_url=CONSTANTS.WSS_URL,
            ping_timeout=self.data_source.WS_HEARTBEAT_TIME_INTERVAL,
        )
        self.assertEqual(1, safe_future_mock.call_count)

    async def test_subscribe_channels_authenticates_and_subscribes(self):
        ws_mock = AsyncMock(spec=WSAssistant)
        self.data_source._authenticate = AsyncMock()

        await self.data_source._subscribe_channels(ws_mock)

        self.data_source._authenticate.assert_awaited_once_with(ws_mock)
        sent_request = ws_mock.send.call_args.args[0]
        self.assertIsInstance(sent_request, WSJSONRequest)
        self.assertEqual(
            {
                "op": "subscribe",
                "data": [
                    CONSTANTS.WS_ORDERS_CHANNEL,
                    CONSTANTS.WS_FILLS_CHANNEL,
                    CONSTANTS.WS_POSITIONS_CHANNEL,
                ],
            },
            sent_request.payload,
        )
        self.assertTrue(self._is_logged("INFO", "Subscribed to private orders, fills and positions channels..."))

    async def test_process_event_message_raises_on_error(self):
        queue = asyncio.Queue()
        event_message = {"error": {"message": "rejected"}}

        with self.assertRaises(IOError) as context:
            await self.data_source._process_event_message(event_message, queue)

        error_payload = context.exception.args[0]
        self.assertEqual("WSS_ERROR", error_payload["label"])
        self.assertIn("rejected", error_payload["message"])

    async def test_process_event_message_routes_channels(self):
        queue = asyncio.Queue()
        event_message = {"channel": CONSTANTS.WS_ORDERS_CHANNEL, "data": {"id": 1}}

        await self.data_source._process_event_message(event_message, queue)

        queued = await queue.get()
        self.assertEqual(event_message, queued)

    async def test_process_websocket_messages_sends_ping_on_timeout(self):
        ws_mock = AsyncMock(spec=WSAssistant)
        ws_mock.send = AsyncMock(side_effect=asyncio.CancelledError)
        queue = asyncio.Queue()

        with patch(
            "hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_user_stream_data_source."
            "UserStreamTrackerDataSource._process_websocket_messages",
            side_effect=asyncio.TimeoutError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source._process_websocket_messages(ws_mock, queue)

        sent_request = ws_mock.send.call_args.args[0]
        self.assertIsInstance(sent_request, WSJSONRequest)
        self.assertEqual({"op": "ping", "id": 1}, sent_request.payload)
