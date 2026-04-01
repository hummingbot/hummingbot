from unittest import TestCase

from hummingbot.connector.exchange.lighter.lighter_utils import (
    LighterConfigMap,
    LighterTestnetConfigMap,
    is_exchange_information_valid,
)


class LighterUtilsTests(TestCase):
    def test_config_map_title(self):
        self.assertEqual("lighter", LighterConfigMap.model_config.get("title"))

    def test_testnet_config_map_title(self):
        self.assertEqual("lighter_testnet", LighterTestnetConfigMap.model_config.get("title"))

    def test_is_exchange_information_valid(self):
        self.assertTrue(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "perp", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": "halted"}))
        self.assertFalse(is_exchange_information_valid({"market_type": "spot", "status": "active"}))
