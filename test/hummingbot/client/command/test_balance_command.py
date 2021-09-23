import asyncio
import unittest
from typing import Awaitable
from unittest.mock import patch, MagicMock

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from test.mock.mock_cli import CLIMockingAssistant


class BalanceCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.app = HummingbotApplication()
        self.cli_mock_assistant = CLIMockingAssistant()
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        super().tearDown()
        self.cli_mock_assistant.stop()

    @staticmethod
    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError

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
        all_balances_all_exchanges_mock.side_effect = self.raise_timeout
        global_config_map["other_commands_timeout"].value = 30

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(self.app.show_balances())
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the balances to update. See logs for more details."
            )
        )
