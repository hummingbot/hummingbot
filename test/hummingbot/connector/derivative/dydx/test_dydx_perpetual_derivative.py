import asyncio
import unittest
from collections import Awaitable
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative import DydxPerpetualDerivative
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class DydxPerpetualDerivativeTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.tracker_task = None
        self.exchange_task = None
        self.log_records = []
        self.return_values_queue = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = DydxPerpetualDerivative(
            dydx_perpetual_api_key="someAPIKey",
            dydx_perpetual_api_secret="someAPISecret",
            dydx_perpetual_passphrase="somePassPhrase",
            dydx_perpetual_account_number=1234,
            dydx_perpetual_ethereum_address="someETHAddress",
            dydx_perpetual_stark_private_key="1234",
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.ev_loop = asyncio.get_event_loop()

    def tearDown(self) -> None:
        self.tracker_task and self.tracker_task.cancel()
        self.exchange_task and self.exchange_task.cancel()
        super().tearDown()

    def simulate_balances_initialized(self, account_balances: Optional[Dict] = None):
        if account_balances is None:
            account_balances = {
                self.quote_asset: Decimal("10"),
                self.base_asset: Decimal("20"),
            }
        self.exchange._account_balances = account_balances

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        logged = any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )
        return logged

    async def return_queued_values_and_unlock_with_event(self):
        val = await self.return_values_queue.get()
        self.resume_test_event.set()
        return val

    def create_exception_and_unlock_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_user_stream_account_ws_message_mock(self, size: float) -> Dict:
        account_message_mock = {
            "contents": self.get_user_stream_account_rest_message_mock(size)
        }
        return account_message_mock

    def get_user_stream_account_rest_message_mock(self, size: float) -> Dict:
        account_message_mock = {
            "account": {
                "equity": "1000",
                "freeCollateral": "10",
                "openPositions": {
                    self.trading_pair: {
                        "market": self.trading_pair,
                        "entryPrice": "10",
                        "size": str(size),
                        "side": "LONG",
                        "unrealizedPnl": "2",
                    }
                }
            }
        }
        return account_message_mock

    def test_user_stream_event_listener_creates_position_from_account_update(self):
        self.exchange_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        position_size = 1
        account_message_mock = self.get_user_stream_account_ws_message_mock(position_size)
        self.return_values_queue.put_nowait(account_message_mock)
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual(1, len(self.exchange.account_positions))

        position = self.exchange.get_position(self.trading_pair)

        self.assertEqual(position_size, position.amount)

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_account")
    def test_update_account_positions_creates_position_from_account_update(self, get_account_mock: AsyncMock):
        self.simulate_balances_initialized()
        position_size = 1
        account_message_mock = self.get_user_stream_account_rest_message_mock(position_size)
        get_account_mock.return_value = account_message_mock

        self.async_run_with_timeout(self.exchange._update_account_positions())

        self.assertEqual(1, len(self.exchange.account_positions))

        position = self.exchange.get_position(self.trading_pair)

        self.assertEqual(position_size, position.amount)
