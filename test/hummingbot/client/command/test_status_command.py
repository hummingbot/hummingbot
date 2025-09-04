import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.mock.mock_cli import CLIMockingAssistant
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication


class StatusCommandTest(IsolatedAsyncioWrapperTestCase):
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

    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    async def test_status_check_all_handles_network_timeouts(self, is_decryption_done_mock, validate_required_connections_mock):
        validate_required_connections_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        self.client_config_map.commands_timeout.other_commands_timeout = 0.01
        is_decryption_done_mock.return_value = True
        strategy_name = "avellaneda_market_making"
        self.app.trading_core.strategy_name = strategy_name
        self.app.strategy_file_name = f"{strategy_name}.yml"

        with self.assertRaises(asyncio.TimeoutError):
            await self.app.status_check_all()
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the connection check to complete. See logs for more details."
            )
        )
