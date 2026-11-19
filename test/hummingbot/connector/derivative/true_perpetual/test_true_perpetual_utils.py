from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.true_perpetual import true_perpetual_utils as utils


class TruePerpetualUtilsTests(TestCase):

    def test_default_fees(self):
        self.assertEqual(Decimal("0.0002"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.00065"), utils.DEFAULT_FEES.taker_percent_fee_decimal)
        self.assertTrue(utils.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_module_constants(self):
        self.assertTrue(utils.CENTRALIZED)
        self.assertEqual("BTC-USDC", utils.EXAMPLE_PAIR)

    def test_config_map_fields(self):
        config = utils.TruePerpetualConfigMap(
            true_perpetual_api_key="tbk_x",
            true_perpetual_api_secret="tbs_y",
        )
        self.assertEqual("true_perpetual", config.connector)
        self.assertEqual("tbk_x", config.true_perpetual_api_key.get_secret_value())
        self.assertEqual("tbs_y", config.true_perpetual_api_secret.get_secret_value())

    def test_config_map_prompts_are_connect_keys(self):
        fields = utils.TruePerpetualConfigMap.model_fields
        for name in ("true_perpetual_api_key", "true_perpetual_api_secret"):
            extra = fields[name].json_schema_extra
            self.assertTrue(extra["is_secure"])
            self.assertTrue(extra["is_connect_key"])
            self.assertTrue(extra["prompt_on_new"])
            self.assertIn("TRUE", extra["prompt"])

    def test_keys_placeholder(self):
        self.assertEqual("true_perpetual", utils.KEYS.connector)
