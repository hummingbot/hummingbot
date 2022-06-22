import asyncio
import unittest
from collections import Awaitable
from unittest.mock import MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap, DBSqliteMode
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange


class TickerCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.app = HummingbotApplication(client_config_map=self.client_config_map)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    def test_show_ticker(self, notify_mock):
        self.client_config_map.db_mode = DBSqliteMode()

        captures = []
        notify_mock.side_effect = lambda s: captures.append(s)

        exchange_name = "paper"
        exchange = MockPaperExchange(client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.app.markets[exchange_name] = exchange
        trading_pair = "BTC-USDT"
        exchange.set_balanced_order_book(
            trading_pair,
            mid_price=10,
            min_price=8.5,
            max_price=11.5,
            price_step_size=1,
            volume_step_size=1,
        )

        self.async_run_with_timeout(self.app.show_ticker(exchange=exchange_name, live=False))

        self.assertEqual(1, len(captures))

        df_str_expected = (
            "   Market: mock_paper_exchange"
            "\n+------------+------------+-------------+--------------+"
            "\n|   Best Bid |   Best Ask |   Mid Price |   Last Trade |"
            "\n|------------+------------+-------------+--------------|"
            "\n|        9.5 |       10.5 |          10 |          nan |"
            "\n+------------+------------+-------------+--------------+"
        )

        self.assertEqual(df_str_expected, captures[0])
