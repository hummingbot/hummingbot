import asyncio
import unittest
from test.mock.mock_cli import CLIMockingAssistant
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap, DBSqliteMode
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
from hummingbot.client.config.security import Security
from hummingbot.client.hummingbot_application import HummingbotApplication


class ConnectCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.app = HummingbotApplication(client_config_map=self.client_config_map)
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        Security._decryption_done.clear()
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

    @patch("hummingbot.client.config.security.Security.wait_til_decryption_done")
    @patch("hummingbot.client.config.security.Security.update_secure_config")
    @patch("hummingbot.client.config.security.Security.connector_config_file_exists")
    @patch("hummingbot.client.config.security.Security.api_keys")
    @patch("hummingbot.user.user_balances.UserBalances.add_exchange")
    def test_connect_exchange_success(
        self,
        add_exchange_mock: AsyncMock,
        api_keys_mock: AsyncMock,
        connector_config_file_exists_mock: MagicMock,
        update_secure_config_mock: MagicMock,
        _: MagicMock,
    ):
        add_exchange_mock.return_value = None
        exchange = "binance"
        api_key = "someKey"
        api_secret = "someSecret"
        api_keys_mock.return_value = {"binance_api_key": api_key, "binance_api_secret": api_secret}
        connector_config_file_exists_mock.return_value = False
        self.cli_mock_assistant.queue_prompt_reply(api_key)  # binance API key
        self.cli_mock_assistant.queue_prompt_reply(api_secret)  # binance API secret

        self.async_run_with_timeout(self.app.connect_exchange(exchange))
        self.assertTrue(self.cli_mock_assistant.check_log_called_with(msg=f"\nYou are now connected to {exchange}."))
        self.assertFalse(self.app.placeholder_mode)
        self.assertFalse(self.app.app.hide_input)
        self.assertEqual(update_secure_config_mock.call_count, 1)

    @patch("hummingbot.client.config.security.Security.wait_til_decryption_done")
    @patch("hummingbot.client.config.security.save_to_yml")
    @patch("hummingbot.client.command.connect_command.CeloCLI")
    @patch("hummingbot.client.config.security.Security.connector_config_file_exists")
    def test_connect_celo_success(
        self,
        connector_config_file_exists_mock: MagicMock,
        celo_cli_mock: MagicMock,
        _: MagicMock,
        __: AsyncMock,
    ):
        connector_config_file_exists_mock.return_value = False
        exchange = "celo"
        celo_address = "someAddress"
        celo_password = "somePassword"
        self.cli_mock_assistant.queue_prompt_reply(celo_address)
        self.cli_mock_assistant.queue_prompt_reply(celo_password)
        celo_cli_mock.validate_node_synced.return_value = None
        celo_cli_mock.unlock_account.return_value = None

        self.async_run_with_timeout(self.app.connect_exchange(exchange))
        self.assertTrue(self.cli_mock_assistant.check_log_called_with(msg="\nYou are now connected to celo."))
        self.assertFalse(self.app.placeholder_mode)
        self.assertFalse(self.app.app.hide_input)

    @patch("hummingbot.client.config.security.Security.wait_til_decryption_done")
    @patch("hummingbot.client.config.security.Security.update_secure_config")
    @patch("hummingbot.client.config.security.Security.connector_config_file_exists")
    @patch("hummingbot.client.config.security.Security.api_keys")
    @patch("hummingbot.user.user_balances.UserBalances.add_exchange")
    def test_connect_exchange_handles_network_timeouts(
        self,
        add_exchange_mock: AsyncMock,
        api_keys_mock: AsyncMock,
        connector_config_file_exists_mock: MagicMock,
        _: MagicMock,
        __: MagicMock,
    ):
        add_exchange_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        self.client_config_map.commands_timeout.other_commands_timeout = 0.01
        api_key = "someKey"
        api_secret = "someSecret"
        api_keys_mock.return_value = {"binance_api_key": api_key, "binance_api_secret": api_secret}
        connector_config_file_exists_mock.return_value = False
        self.cli_mock_assistant.queue_prompt_reply(api_key)  # binance API key
        self.cli_mock_assistant.queue_prompt_reply(api_secret)  # binance API secret

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(self.app.connect_exchange("binance"))
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the connection to complete. See logs for more details."
            )
        )
        self.assertFalse(self.app.placeholder_mode)
        self.assertFalse(self.app.app.hide_input)

    @patch("hummingbot.user.user_balances.UserBalances.update_exchanges")
    @patch("hummingbot.client.config.security.Security.wait_til_decryption_done")
    def test_connection_df_handles_network_timeouts(self, _: AsyncMock, update_exchanges_mock: AsyncMock):
        update_exchanges_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        self.client_config_map.commands_timeout.other_commands_timeout = 0.01

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(self.app.connection_df())
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the connection table to populate. See logs for more details."
            )
        )

    @patch("hummingbot.user.user_balances.UserBalances.update_exchanges")
    @patch("hummingbot.client.config.security.Security.wait_til_decryption_done")
    def test_connection_df_handles_network_timeouts_logs_hidden(self, _: AsyncMock, update_exchanges_mock: AsyncMock):
        self.cli_mock_assistant.toggle_logs()

        update_exchanges_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        self.client_config_map.commands_timeout.other_commands_timeout = 0.01

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(self.app.connection_df())
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the connection table to populate. See logs for more details."
            )
        )

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.connection_df")
    def test_show_connections(self, connection_df_mock, notify_mock):
        self.client_config_map.db_mode = DBSqliteMode()

        Security._decryption_done.set()

        captures = []
        notify_mock.side_effect = lambda s: captures.append(s)

        connections_df = pd.DataFrame(
            columns=pd.Index(['Exchange', '  Keys Added', '  Keys Confirmed', '  Status'], dtype='object'),
            data=[
                ["ascend_ex", "Yes", "Yes", "&cYELLOW"],
                ["beaxy", "Yes", "Yes", "&cGREEN"]
            ]
        )
        connection_df_mock.return_value = (connections_df, [])

        self.async_run_with_timeout(self.app.show_connections())

        self.assertEqual(2, len(captures))
        self.assertEqual("\nTesting connections, please wait...", captures[0])

        df_str_expected = (
            "    +------------+----------------+--------------------+------------+"
            "\n    | Exchange   |   Keys Added   |   Keys Confirmed   |   Status   |"
            "\n    |------------+----------------+--------------------+------------|"
            "\n    | ascend_ex  | Yes            | Yes                | &cYELLOW   |"
            "\n    | beaxy      | Yes            | Yes                | &cGREEN    |"
            "\n    +------------+----------------+--------------------+------------+"
        )

        self.assertEqual(df_str_expected, captures[1])
