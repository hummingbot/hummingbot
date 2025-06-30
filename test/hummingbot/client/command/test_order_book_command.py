from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.mock.mock_cli import CLIMockingAssistant
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap, DBSqliteMode
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange


class OrderBookCommandTest(IsolatedAsyncioWrapperTestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    @patch("hummingbot.core.gateway.gateway_status_monitor.GatewayStatusMonitor.start")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.mqtt_start")
    async def asyncSetUp(self, mock_mqtt_start, mock_gateway_start, mock_trading_pair_fetcher):
        await read_system_configs_from_yml()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.app = HummingbotApplication(client_config_map=self.client_config_map)
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    async def test_show_order_book(self, notify_mock):
        self.client_config_map.db_mode = DBSqliteMode()

        captures = []
        notify_mock.side_effect = lambda s: captures.append(s)

        exchange_name = "paper"
        exchange = MockPaperExchange(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        # Set the exchange in the new architecture location
        self.app.trading_core.connector_manager.connectors[exchange_name] = exchange
        trading_pair = "BTC-USDT"
        exchange.set_balanced_order_book(
            trading_pair,
            mid_price=10,
            min_price=8.5,
            max_price=11.5,
            price_step_size=1,
            volume_step_size=1,
        )

        await self.app.show_order_book(exchange=exchange_name, live=False)

        self.assertEqual(1, len(captures))

        df_str_expected = (
            "  market: mock_paper_exchange BTC-USDT"
            "\n    +-------------+--------------+-------------+--------------+"
            "\n    |   bid_price |   bid_volume |   ask_price |   ask_volume |"
            "\n    |-------------+--------------+-------------+--------------|"
            "\n    |         9.5 |            1 |        10.5 |            1 |"
            "\n    |         8.5 |            2 |        11.5 |            2 |"
            "\n    +-------------+--------------+-------------+--------------+"
        )

        self.assertEqual(df_str_expected, captures[0])
