import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hummingbot.connector.exchange.kuru import kuru_constants as CONSTANTS
from hummingbot.connector.exchange.kuru.kuru_utils import (
    get_current_server_time,
    get_market_config,
    trading_pair_from_market_config,
)


class TestKuruUtils(unittest.TestCase):

    def test_get_market_config_returns_known_market_case_insensitively(self):
        config = get_market_config("0x065c9d28e428a0db40191a54d33d5b7c71a9c394")

        self.assertEqual("MON-USDC", config.market_symbol)

    @patch("hummingbot.connector.exchange.kuru.kuru_utils.ConfigManager.load_market_config")
    def test_get_market_config_loads_unknown_market_with_default_rpc(self, load_market_config_mock):
        expected = SimpleNamespace(market_symbol="TEST-USDC")
        load_market_config_mock.return_value = expected

        config = get_market_config("0xabc")

        self.assertIs(expected, config)
        load_market_config_mock.assert_called_once_with(
            market_address="0xabc",
            rpc_url=CONSTANTS.DEFAULT_RPC_URL,
        )

    @patch("hummingbot.connector.exchange.kuru.kuru_utils.ConfigManager.load_market_config")
    def test_get_market_config_uses_custom_rpc_for_unknown_market(self, load_market_config_mock):
        expected = SimpleNamespace(market_symbol="TEST-USDC")
        load_market_config_mock.return_value = expected

        config = get_market_config("0xdef", rpc_url="https://custom-rpc")

        self.assertIs(expected, config)
        load_market_config_mock.assert_called_once_with(
            market_address="0xdef",
            rpc_url="https://custom-rpc",
        )

    def test_trading_pair_from_market_config_returns_market_symbol(self):
        market_config = SimpleNamespace(market_symbol="MON-USDC")

        self.assertEqual("MON-USDC", trading_pair_from_market_config(market_config))

    @patch("hummingbot.connector.exchange.kuru.kuru_utils.time.time", return_value=1234.5)
    def test_get_current_server_time_returns_float_timestamp(self, _):
        self.assertEqual(1234.5, get_current_server_time())
        self.assertIsInstance(get_current_server_time(), float)
