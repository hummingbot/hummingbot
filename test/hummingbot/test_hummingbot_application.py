import unittest
from unittest.mock import patch, MagicMock

from hummingbot.client.hummingbot_application import HummingbotApplication


class HummingbotApplicationTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app = HummingbotApplication()

    @patch("hummingbot.model.sql_connection_manager.SQLConnectionManager.get_trade_fills_instance")
    def test_set_strategy_file_name(self, mock: MagicMock):
        strategy_name = "some-strategy"
        file_name = f"{strategy_name}.yml"
        self.app.strategy_file_name = file_name

        self.assertEqual(file_name, self.app.strategy_file_name)
        mock.assert_called_with(strategy_name)

    @patch("hummingbot.model.sql_connection_manager.SQLConnectionManager.get_trade_fills_instance")
    def test_set_strategy_file_name_to_none(self, mock: MagicMock):
        strategy_name = "some-strategy"
        file_name = f"{strategy_name}.yml"

        self.app.strategy_file_name = None

        self.assertEqual(None, self.app.strategy_file_name)
        mock.assert_not_called()

        self.app.strategy_file_name = file_name
        self.app.strategy_file_name = None

        self.assertEqual(None, self.app.strategy_file_name)
        self.assertEqual(1, mock.call_count)
