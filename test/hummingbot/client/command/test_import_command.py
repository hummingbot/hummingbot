import asyncio
import unittest
from typing import Awaitable
from unittest.mock import patch, MagicMock, AsyncMock

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication
from test.mock.mock_cli import CLIMockingAssistant


class ImportCommandTest(unittest.TestCase):
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

    @patch("hummingbot.client.command.import_command.update_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_import_config_file_success(
        self, status_check_all_mock: AsyncMock, update_strategy_config_map_from_file: AsyncMock
    ):
        strategy_name = "some-strategy"
        strategy_file_name = f"{strategy_name}.yml"
        status_check_all_mock.return_value = True
        update_strategy_config_map_from_file.return_value = strategy_name

        self.async_run_with_timeout(self.app.import_config_file(strategy_file_name))
        self.assertEqual(strategy_file_name, self.app.strategy_file_name)
        self.assertEqual(strategy_name, self.app.strategy_name)
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with("\nEnter \"start\" to start market making.")
        )

    @patch("hummingbot.client.command.import_command.update_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    def test_import_config_file_handles_network_timeouts(
        self, status_check_all_mock: AsyncMock, update_strategy_config_map_from_file: AsyncMock
    ):
        strategy_name = "some-strategy"
        strategy_file_name = f"{strategy_name}.yml"
        status_check_all_mock.side_effect = self.raise_timeout
        update_strategy_config_map_from_file.return_value = strategy_name

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(
                self.app.import_config_file(strategy_file_name)
            )
        self.assertEqual(None, self.app.strategy_file_name)
        self.assertEqual(None, self.app.strategy_name)
