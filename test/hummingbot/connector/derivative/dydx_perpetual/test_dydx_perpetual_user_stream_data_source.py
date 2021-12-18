import asyncio
import unittest

from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper import DydxPerpetualClientWrapper
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source import (
    DydxPerpetualUserStreamDataSource,
)
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class DydxPerpetualUserStreamDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.api_key = "someKey"
        cls.api_secret = "someSecretKey"
        cls.passphrase = "somePassphrase"
        cls.account_number = "someAccountNumber"
        cls.stark_private_key = "A" * 16
        cls.eth_address = "someEthAddress"
        cls.dydx_client = DydxPerpetualClientWrapper(
            api_key=cls.api_key,
            api_secret=cls.api_secret,
            passphrase=cls.passphrase,
            account_number=cls.account_number,
            stark_private_key=cls.stark_private_key,
            ethereum_address=cls.eth_address,
        )
        cls.dydx_auth = DydxPerpetualAuth(cls.dydx_client)

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None

        self.data_source = DydxPerpetualUserStreamDataSource(self.dydx_auth)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource._sleep")
    def test_listen_for_user_stream_raises_cancelled_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(self.ev_loop, asyncio.Queue()))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth.DydxPerpetualAuth.get_ws_auth_params")
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource._sleep")
    def test_listen_for_user_stream_raises_logs_exception(self, mock_sleep, mock_auth, ws_connect_mock):
        mock_sleep.side_effect = lambda: (
            self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        )
        mock_auth.return_value = {}
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda *_: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, asyncio.Queue()))

        self.async_run_with_timeout(self.resume_test_event.wait(), 1.0)

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error with dydx WebSocket connection. Retrying after 30 seconds..."
            )
        )
