import asyncio
import json
import unittest
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.foxbit import foxbit_constants as CONSTANTS
from hummingbot.connector.exchange.foxbit.foxbit_api_user_stream_data_source import FoxbitAPIUserStreamDataSource
from hummingbot.connector.exchange.foxbit.foxbit_auth import FoxbitAuth
from hummingbot.connector.exchange.foxbit.foxbit_exchange import FoxbitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


@patch("hummingbot.connector.exchange.foxbit.foxbit_api_user_stream_data_source.FoxbitAPIUserStreamDataSource._sleep", new_callable=AsyncMock)
class FoxbitUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self._api_key = "testApiKey"
        self._secret = "testSecret"
        self._user_id = "testUserId"
        self.auth = FoxbitAuth(api_key=self._api_key, secret_key=self._secret, user_id=self._user_id, time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        self.connector = FoxbitExchange(
            foxbit_api_key="testAPIKey",
            foxbit_api_secret="testSecret",
            foxbit_user_id="testUserId",
            trading_pairs=[self.trading_pair],
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = FoxbitAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _error_response(self) -> Dict[str, Any]:
        resp = {
            "code": "ERROR CODE",
            "msg": "ERROR MESSAGE"
        }

        return resp

    def _user_update_event(self):
        # Balance Update
        resp = {
            "e": "balanceUpdate",
            "E": 1573200697110,
            "a": "BTC",
            "d": "100.00000000",
            "T": 1573200697068
        }
        return json.dumps(resp)

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    def test_user_stream_properties(self, mock_sleep):
        self.assertEqual(self.data_source.ready, self.data_source._user_stream_data_source_initialized)

    @patch("hummingbot.connector.exchange.foxbit.foxbit_api_user_stream_data_source.web_utils.websocket_url", return_value="wss://test")
    @patch("hummingbot.connector.exchange.foxbit.foxbit_api_user_stream_data_source.WSAssistant")
    def test_connected_websocket_assistant_success(self, mock_ws_assistant_cls, mock_websocket_url, mock_sleep):
        # Arrange
        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        mock_ws.send = AsyncMock()
        # Simulate authenticated response
        mock_ws.receive = AsyncMock(return_value=MagicMock(data={"o": '{"Authenticated": True}'}))
        mock_ws_assistant_cls.return_value = mock_ws

        mock_api_factory = MagicMock()
        mock_api_factory.get_ws_assistant = AsyncMock(return_value=mock_ws)

        auth = MagicMock()
        auth.get_ws_authenticate_payload.return_value = {"test": "payload"}

        data_source = FoxbitAPIUserStreamDataSource(
            auth=auth,
            trading_pairs=["COINALPHA-HBOT"],
            connector=MagicMock(),
            api_factory=mock_api_factory,
            domain="com"
        )

        # Act
        ws = self.async_run_with_timeout(data_source._connected_websocket_assistant())

        # Assert
        self.assertIs(ws, mock_ws)
        mock_ws.connect.assert_awaited_once()
        mock_ws.send.assert_awaited()
        mock_ws.receive.assert_awaited()

    async def test_run_ws_assistant(self, mock_sleep):
        ws: WSAssistant = await self.data_source._connected_websocket_assistant()
        self.assertIsNotNone(ws)
        await self.data_source._subscribe_channels(ws)
        await self.data_source._on_user_stream_interruption(ws)
