from unittest import TestCase

from hummingbot.connector.exchange.lighter.lighter_utils import LighterConfigMap, LighterTestnetConfigMap


class LighterUtilsTests(TestCase):
    def test_config_map_title(self):
        self.assertEqual("lighter", LighterConfigMap.model_config.get("title"))

    def test_testnet_config_map_title(self):
        self.assertEqual("lighter_testnet", LighterTestnetConfigMap.model_config.get("title"))
