import asyncio
import unittest
from decimal import Decimal
from test.mock.mock_cli import CLIMockingAssistant
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication


class BalanceCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())

        self.app = HummingbotApplication()
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        super().tearDown()

    @staticmethod
    def get_async_sleep_fn(delay: float):
        async def async_sleep(*_, **__):
            await asyncio.sleep(delay)
        return async_sleep

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def async_run_with_timeout_coroutine_must_raise_timeout(self, coroutine: Awaitable, timeout: float = 1):
        class DesiredError(Exception):
            pass

        async def run_coro_that_raises(coro: Awaitable):
            try:
                await coro
            except asyncio.TimeoutError:
                raise DesiredError

        try:
            self.async_run_with_timeout(run_coro_that_raises(coroutine), timeout)
        except DesiredError:  # the coroutine raised an asyncio.TimeoutError as expected
            raise asyncio.TimeoutError
        except asyncio.TimeoutError:  # the coroutine did not finish on time
            raise RuntimeError

    @patch("hummingbot.user.user_balances.UserBalances.all_balances_all_exchanges")
    def test_show_balances_handles_network_timeouts(
        self, all_balances_all_exchanges_mock
    ):
        all_balances_all_exchanges_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        self.app.client_config_map.commands_timeout.other_commands_timeout = Decimal("0.01")

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(self.app.show_balances())
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the balances to update. See logs for more details."
            )
        )

    @patch("hummingbot.user.user_balances.UserBalances.all_available_balances_all_exchanges")
    @patch("hummingbot.user.user_balances.UserBalances.all_balances_all_exchanges")
    def test_show_balances_empty_balances(
        self,
        all_balances_all_exchanges_mock: AsyncMock,
        all_available_balances_all_exchanges_mock: AsyncMock,
    ):
        all_balances_all_exchanges_mock.return_value = {"binance": {}}
        all_available_balances_all_exchanges_mock.return_value = {"binance": {}}

        self.async_run_with_timeout(self.app.show_balances())

        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg="\nbinance:")
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg="You have no balance on this exchange.")
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg=f"\n\nExchanges Total: {self.app.client_config_map.global_token.global_token_symbol} 0    "
            )
        )

    @patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle.get_rate")
    @patch("hummingbot.user.user_balances.UserBalances.all_available_balances_all_exchanges")
    @patch("hummingbot.user.user_balances.UserBalances.all_balances_all_exchanges")
    def test_show_balances(
        self,
        all_balances_all_exchanges_mock: AsyncMock,
        all_available_balances_all_exchanges_mock: AsyncMock,
        get_rate_mock: AsyncMock,
    ):
        all_balances_all_exchanges_mock.return_value = {
            "binance": {"BTC": Decimal("10")},
        }
        all_available_balances_all_exchanges_mock.return_value = {
            "binance": {"BTC": Decimal("5")},
        }
        get_rate_mock.return_value = Decimal("2")

        self.async_run_with_timeout(self.app.show_balances())

        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg="\nbinance:")
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg=(
                    f"    Asset   Total Total ({self.app.client_config_map.global_token.global_token_symbol}) Allocated"
                    f"\n      BTC 10.0000     20.00       50%"
                )
            )
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg=f"\n  Total: {self.app.client_config_map.global_token.global_token_symbol} 20.00"
            )
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(msg="Allocated: 50.00%")
        )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg=f"\n\nExchanges Total: {self.app.client_config_map.global_token.global_token_symbol} 20    "
            )
        )
