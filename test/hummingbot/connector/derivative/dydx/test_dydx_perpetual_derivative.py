import asyncio
import unittest
from collections import Awaitable
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative import DydxPerpetualDerivative
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_position import DydxPerpetualPosition
from hummingbot.core.event.events import PositionSide


class DydxPerpetualDerivativeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.exchange_task = None
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

        self.ev_loop = asyncio.get_event_loop()

    def tearDown(self) -> None:
        self.exchange_task and self.exchange_task.cancel()
        super().tearDown()

    def simulate_balances_initialized(self, account_balances: Optional[Dict] = None):
        if account_balances is None:
            account_balances = {
                self.quote_asset: Decimal("10"),
                self.base_asset: Decimal("20"),
            }
        self.exchange._account_balances = account_balances

    async def return_queued_values_and_unlock_with_event(self):
        val = await self.return_values_queue.get()
        self.resume_test_event.set()
        return val

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_user_stream_account_ws_message_mock(self, size: float, status: str = "OPEN") -> Dict:
        account_message_mock = {
            "contents": self.get_account_rest_message_mock(size, status)
        }
        return account_message_mock

    def get_account_rest_message_mock(self, size: float, status: str = "OPEN") -> Dict:
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
                        "status": status,
                    }
                }
            }
        }
        return account_message_mock

    def get_user_stream_positions_ws_message_mock(self, size: float, status: str = "OPEN") -> Dict:
        positions_message_mock = {
            "contents": self.get_positions_rest_message_mock(size, status)
        }
        return positions_message_mock

    def get_positions_rest_message_mock(self, size: float, status: str = "OPEN") -> Dict:
        positions_message_mock = {
            "positions": [
                {
                    "market": self.trading_pair,
                    "side": "LONG",
                    "unrealizedPnl": "2",
                    "size": str(size),
                    "status": status,
                }
            ]
        }
        return positions_message_mock

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

    def test_user_stream_event_listener_updates_position_from_positions_update(self):
        self.exchange_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        position_size = 1
        account_message_mock = self.get_user_stream_positions_ws_message_mock(position_size, status="CLOSED")
        self.return_values_queue.put_nowait(account_message_mock)
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        position = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.LONG,
            unrealized_pnl=Decimal("2"),
            entry_price=Decimal("1"),
            amount=Decimal(position_size) / 2,
            leverage=Decimal("10"),
        )
        self.exchange._account_positions[self.trading_pair] = position

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertEqual(position_size, position.amount)  # position was updated with message
        self.assertEqual(0, len(self.exchange.account_positions))  # closed position removed

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_account")
    def test_update_account_positions_creates_position_from_account_update(self, get_account_mock: AsyncMock):
        self.simulate_balances_initialized()
        position_size = 1
        account_message_mock = self.get_account_rest_message_mock(position_size)
        get_account_mock.return_value = account_message_mock

        self.async_run_with_timeout(self.exchange._update_account_positions())

        self.assertEqual(1, len(self.exchange.account_positions))

        position = self.exchange.get_position(self.trading_pair)

        self.assertEqual(position_size, position.amount)

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_account")
    def test_update_account_positions_updates_position_from_account_update(self, get_account_mock: AsyncMock):
        self.simulate_balances_initialized()
        position_size = 1
        account_message_mock = self.get_account_rest_message_mock(position_size, status="CLOSED")
        get_account_mock.return_value = account_message_mock

        position = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.LONG,
            unrealized_pnl=Decimal("2"),
            entry_price=Decimal("1"),
            amount=Decimal(position_size) / 2,
            leverage=Decimal("10"),
        )
        self.exchange._account_positions[self.trading_pair] = position

        self.async_run_with_timeout(self.exchange._update_account_positions())

        self.assertEqual(position_size, position.amount)  # position was updated with message
        self.assertEqual(0, len(self.exchange.account_positions))  # closed position removed
