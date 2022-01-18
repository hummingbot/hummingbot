import asyncio
import time
import pandas as pd
import unittest

from collections import Awaitable
from datetime import datetime
from decimal import Decimal
from dydx3 import DydxApiError
from typing import Dict, Optional
from unittest.mock import AsyncMock, PropertyMock, patch
from requests import Response


from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative import DydxPerpetualDerivative
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_position import DydxPerpetualPosition
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.event.events import PositionSide, FundingInfo


class DydxPerpetualDerivativeTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()

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
        self.log_records = []

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

        self.ev_loop = asyncio.get_event_loop()

    def tearDown(self) -> None:
        self.exchange_task and self.exchange_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def check_is_logged(self, log_level: str, message: str) -> bool:
        is_logged = any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )
        return is_logged

    def simulate_balances_initialized(self, account_balances: Optional[Dict] = None):
        if account_balances is None:
            account_balances = {
                self.quote_asset: Decimal("10"),
                self.base_asset: Decimal("20"),
            }
        self.exchange._account_balances = account_balances

    def _simulate_reset_poll_notifier(self):
        self.exchange._poll_notifier.clear()

    def _simulate_ws_message_received(self, timestamp: float):
        self.exchange._user_stream_tracker._data_source._ws_assistant._connection._last_recv_time = timestamp

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

    def get_markets_message_mock(
        self,
        index_price: float = 1,
        min_order_size: float = 2,
        min_price_increment: float = 3,
        min_base_amount_increment: float = 4,
    ) -> Dict:
        markets_message_mock = {  # irrelevant fields removed
            "markets": {
                self.trading_pair: {
                    "quoteAsset": self.quote_asset,
                    "minOrderSize": str(min_order_size),
                    "tickSize": str(min_price_increment),
                    "stepSize": str(min_base_amount_increment),
                    "indexPrice": str(index_price),
                    "oraclePrice": "10.1",
                    "nextFundingAt": str(datetime.now()),
                    "nextFundingRate": "0.1",
                    "initialMarginFraction": "0.1",
                    "maintenanceMarginFraction": "0.2",
                }
            }
        }
        return markets_message_mock

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

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_markets")
    def test_update_funding_rates_succeeds(self, get_markets_mock: AsyncMock):
        index_price = 10.0
        markets_message_mock = self.get_markets_message_mock(index_price)
        get_markets_mock.return_value = markets_message_mock

        self.async_run_with_timeout(self.exchange._update_funding_rates())

        funding_info = self.exchange.get_funding_info(self.trading_pair)

        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(Decimal(index_price), funding_info.index_price)

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_markets")
    def test_update_funding_fails_on_rate_limit(self, get_markets_mock: AsyncMock):
        resp = Response()
        resp.status_code = 429
        resp._content = b'{"errors": [{"msg": "Too many requests"}]}'
        get_markets_mock.return_value = DydxApiError(resp)

        self.async_run_with_timeout(self.exchange._update_funding_rates())

        self.check_is_logged(log_level="NETWORK", message="Rate-limit error.")

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_markets")
    def test_update_funding_fails_on_other_dydx_api_error(self, get_markets_mock: AsyncMock):
        resp = Response()
        resp.status_code = 430
        resp._content = b'{"errors": [{"msg": "Some other dydx API error."}]}'
        get_markets_mock.return_value = DydxApiError(resp)

        self.async_run_with_timeout(self.exchange._update_funding_rates())

        self.check_is_logged(log_level="NETWORK", message="dYdX API error.")

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_markets")
    def test_update_funding_fails_on_general_exception(self, get_markets_mock: AsyncMock):
        get_markets_mock.return_value = Exception("Dummy exception")

        self.async_run_with_timeout(self.exchange._update_funding_rates())

        self.check_is_logged(log_level="NETWORK", message="Unknown error.")

    def test_tick_initial_tick_successful(self):
        start_ts: float = time.time() * 1e3

        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative.DydxPerpetualDerivative.time_now_s")
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource.last_recv_time", new_callable=PropertyMock)
    def test_tick_subsequent_tick_within_short_poll_interval(self, mock_last_recv_time, mock_ts):
        # Assumes user stream tracker has NOT been receiving messages, Hence SHORT_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.SHORT_POLL_INTERVAL - 1)

        mock_ts.return_value = start_ts
        mock_last_recv_time.return_value = -1

        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_reset_poll_notifier()

        # Simulate last message received 1 sec ago
        mock_last_recv_time.return_value = next_tick - 1

        mock_ts.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_poll_timestamp)
        self.assertFalse(self.exchange._poll_notifier.is_set())

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative.DydxPerpetualDerivative.time_now_s")
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource.last_recv_time", new_callable=PropertyMock)
    def test_tick_subsequent_tick_exceed_short_poll_interval(self, mock_last_recv_time, mock_ts):
        # Assumes user stream tracker has NOT been receiving messages, Hence SHORT_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.SHORT_POLL_INTERVAL + 1)

        mock_ts.return_value = start_ts
        mock_last_recv_time.return_value = -1

        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        self._simulate_reset_poll_notifier()

        mock_ts.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative.DydxPerpetualDerivative.time_now_s")
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource.last_recv_time", new_callable=PropertyMock)
    def test_tick_subsequent_tick_within_long_poll_interval(self, mock_last_recv_time, mock_time):

        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.LONG_POLL_INTERVAL - 1)

        mock_time.return_value = start_ts
        mock_last_recv_time.return_value = -1

        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        # Simulate last message received 1 sec ago
        mock_last_recv_time.return_value = next_tick - 1
        self._simulate_reset_poll_notifier()

        mock_time.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_poll_timestamp)
        self.assertFalse(self.exchange._poll_notifier.is_set())

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative.DydxPerpetualDerivative.time_now_s")
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource.last_recv_time", new_callable=PropertyMock)
    def test_tick_subsequent_tick_exceed_long_poll_interval(self, mock_last_recv_time, mock_time):
        # Assumes user stream tracker has been receiving messages, Hence LONG_POLL_INTERVAL in use
        start_ts: float = self.start_timestamp
        next_tick: float = start_ts + (self.exchange.LONG_POLL_INTERVAL - 1)

        mock_last_recv_time.return_value = -1
        mock_time.return_value = start_ts
        self.exchange.tick(start_ts)
        self.assertEqual(start_ts, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

        mock_last_recv_time.return_value = start_ts
        self._simulate_reset_poll_notifier()

        mock_time.return_value = next_tick
        self.exchange.tick(next_tick)
        self.assertEqual(next_tick, self.exchange._last_poll_timestamp)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_markets")
    def test_update_trading_rules(self, get_markets_mock: AsyncMock):
        min_order_size = 1
        min_price_increment = 2
        min_base_amount_increment = 3
        min_notional_size = min_order_size * min_price_increment
        markets_message_mock = self.get_markets_message_mock(
            min_order_size=min_order_size,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
        )
        get_markets_mock.return_value = markets_message_mock

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        trading_rule: TradingRule = self.exchange._trading_rules[self.trading_pair]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_base_amount_increment, trading_rule.min_base_amount_increment)
        self.assertEqual(min_notional_size, trading_rule.min_notional_size)
        self.assertEqual(self.quote_asset, trading_rule.buy_order_collateral_token)
        self.assertEqual(self.quote_asset, trading_rule.sell_order_collateral_token)

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_client_wrapper"
           ".DydxPerpetualClientWrapper.get_markets")
    def test_get_buy_and_sell_collateral_token(self, get_markets_mock: AsyncMock):
        markets_message_mock = self.get_markets_message_mock()
        get_markets_mock.return_value = markets_message_mock

        self.async_run_with_timeout(self.exchange._update_trading_rules())
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, buy_collateral_token)
        self.assertEqual(self.quote_asset, sell_collateral_token)
