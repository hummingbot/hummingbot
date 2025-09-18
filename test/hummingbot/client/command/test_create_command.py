import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.mock.mock_cli import CLIMockingAssistant
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    get_strategy_config_map,
    read_system_configs_from_yml,
)
from hummingbot.client.hummingbot_application import HummingbotApplication


class CreateCommandTest(IsolatedAsyncioWrapperTestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.start_monitor")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.mqtt_start")
    async def asyncSetUp(self, mock_mqtt_start, mock_gateway_start, mock_trading_pair_fetcher):
        await read_system_configs_from_yml()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.app = HummingbotApplication(client_config_map=self.client_config_map)
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

    @patch("shutil.copy")
    @patch("hummingbot.client.command.create_command.save_to_yml_legacy")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.core.utils.market_price.get_last_price")
    async def test_prompt_for_configuration_re_prompts_on_lower_than_minimum_amount(
        self,
        get_last_price_mock: AsyncMock,
        validate_required_connections_mock: AsyncMock,
        is_decryption_done_mock: MagicMock,
        save_to_yml_mock: MagicMock,
        _: MagicMock,
    ):
        get_last_price_mock.return_value = Decimal("11")
        validate_required_connections_mock.return_value = {}
        is_decryption_done_mock.return_value = True
        config_maps = []
        save_to_yml_mock.side_effect = lambda _, cm: config_maps.append(cm)

        self.client_config_map.commands_timeout.create_command_timeout = 10
        self.client_config_map.commands_timeout.other_commands_timeout = 30
        strategy_name = "some-strategy"
        strategy_file_name = f"{strategy_name}.yml"
        base_strategy = "pure_market_making"
        self.cli_mock_assistant.queue_prompt_reply(base_strategy)  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("0")  # unacceptable order amount
        self.cli_mock_assistant.queue_prompt_reply("1")  # acceptable order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature
        self.cli_mock_assistant.queue_prompt_reply(strategy_file_name)  # ping pong feature

        self.app.app.to_stop_config = False  # Disable stop config to allow the test to complete
        await self.app.prompt_for_configuration()
        await asyncio.sleep(0.0001)  # Allow time for the prompt to process
        self.assertEqual(base_strategy, self.app.strategy_name)
        self.assertTrue(self.cli_mock_assistant.check_log_called_with(msg="Value must be more than 0."))

    @patch("shutil.copy")
    @patch("hummingbot.client.command.create_command.save_to_yml_legacy")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.core.utils.market_price.get_last_price")
    async def test_prompt_for_configuration_accepts_zero_amount_on_get_last_price_network_timeout(
        self,
        get_last_price_mock: AsyncMock,
        validate_required_connections_mock: AsyncMock,
        is_decryption_done_mock: MagicMock,
        save_to_yml_mock: MagicMock,
        _: MagicMock,
    ):
        get_last_price_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        validate_required_connections_mock.return_value = {}
        is_decryption_done_mock.return_value = True
        config_maps = []
        save_to_yml_mock.side_effect = lambda _, cm: config_maps.append(cm)

        self.client_config_map.commands_timeout.create_command_timeout = 0.005
        self.client_config_map.commands_timeout.other_commands_timeout = 0.01
        strategy_name = "some-strategy"
        strategy_file_name = f"{strategy_name}.yml"
        base_strategy = "pure_market_making"
        self.cli_mock_assistant.queue_prompt_reply(base_strategy)  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("1")  # order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature
        self.cli_mock_assistant.queue_prompt_reply(strategy_file_name)
        self.app.app.to_stop_config = False  # Disable stop config to allow the test to complete
        await self.app.prompt_for_configuration()
        await asyncio.sleep(0.01)
        self.assertEqual(base_strategy, self.app.strategy_name)

    async def test_create_command_restores_config_map_after_config_stop(self):
        base_strategy = "pure_market_making"
        strategy_config = get_strategy_config_map(base_strategy)
        original_exchange = "bybit"
        strategy_config["exchange"].value = original_exchange

        self.cli_mock_assistant.queue_prompt_reply(base_strategy)  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_to_stop_config()  # cancel on trading pair prompt

        await self.app.prompt_for_configuration()
        await asyncio.sleep(0.0001)
        strategy_config = get_strategy_config_map(base_strategy)

        self.assertEqual(original_exchange, strategy_config["exchange"].value)

    async def test_create_command_restores_config_map_after_config_stop_on_new_file_prompt(self):
        base_strategy = "pure_market_making"
        strategy_config = get_strategy_config_map(base_strategy)
        original_exchange = "bybit"
        strategy_config["exchange"].value = original_exchange

        self.cli_mock_assistant.queue_prompt_reply(base_strategy)  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("1")  # order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature
        self.cli_mock_assistant.queue_prompt_to_stop_config()  # cancel on new file prompt
        self.app.app.to_stop_config = False
        await self.app.prompt_for_configuration()
        await asyncio.sleep(0.0001)
        strategy_config = get_strategy_config_map(base_strategy)

        self.assertEqual(original_exchange, strategy_config["exchange"].value)

    @patch("shutil.copy")
    @patch("hummingbot.client.command.create_command.save_to_yml_legacy")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.core.utils.market_price.get_last_price")
    async def test_prompt_for_configuration_handles_status_network_timeout(
        self,
        get_last_price_mock: AsyncMock,
        validate_required_connections_mock: AsyncMock,
        is_decryption_done_mock: MagicMock,
        _: MagicMock,
        __: MagicMock,
    ):
        get_last_price_mock.return_value = None
        validate_required_connections_mock.side_effect = self.get_async_sleep_fn(delay=0.05)
        is_decryption_done_mock.return_value = True
        strategy_file_name = "some-strategy.yml"
        self.cli_mock_assistant.queue_prompt_reply("pure_market_making")  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("1")  # order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature
        self.cli_mock_assistant.queue_prompt_reply(strategy_file_name)
        self.app.client_config_map.commands_timeout.create_command_timeout = Decimal(0.005)
        self.app.client_config_map.commands_timeout.other_commands_timeout = Decimal(0.01)

        with self.assertRaises(asyncio.TimeoutError):
            self.app.app.to_stop_config = False
            await self.app.prompt_for_configuration()
            await asyncio.sleep(0.01)
        self.assertEqual(None, self.app.strategy_file_name)
        self.assertEqual(None, self.app.strategy_name)
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the connection check to complete. See logs for more details."
            )
        )
