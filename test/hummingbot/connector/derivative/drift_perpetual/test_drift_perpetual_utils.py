from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.drift_perpetual import drift_perpetual_utils as utils
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


class DriftPerpetualUtilsTests(TestCase):

    def test_connector_is_decentralized(self):
        # Drift is a Solana DEX perp; it must not be flagged as centralized.
        self.assertFalse(utils.CENTRALIZED)

    def test_example_pair_is_perp_formatted(self):
        self.assertEqual("SOL-PERP", utils.EXAMPLE_PAIR)

    def test_default_fees_schema(self):
        self.assertIsInstance(utils.DEFAULT_FEES, TradeFeeSchema)
        self.assertEqual(Decimal("0.0000"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0010"), utils.DEFAULT_FEES.taker_percent_fee_decimal)

    def test_config_map_defaults(self):
        cfg = utils.DriftPerpetualConfigMap.model_construct()
        self.assertEqual("drift_perpetual", cfg.connector)
        self.assertEqual("127.0.0.1", cfg.drift_perpetual_gateway_host)
        self.assertEqual(8080, cfg.drift_perpetual_gateway_rest_port)
        self.assertEqual(1337, cfg.drift_perpetual_gateway_ws_port)
        self.assertEqual(0, cfg.drift_perpetual_sub_account_id)

    def test_config_map_does_not_request_private_key(self):
        # The gateway holds the Solana keypair; the connector must never
        # prompt for a secret. Guards against an accidental key field.
        fields = set(utils.DriftPerpetualConfigMap.model_fields.keys())
        for forbidden in ("private_key", "secret_key", "drift_perpetual_private_key"):
            self.assertNotIn(forbidden, fields)

    def test_keys_singleton_is_config_map(self):
        self.assertIsInstance(utils.KEYS, utils.DriftPerpetualConfigMap)
        self.assertEqual("drift_perpetual", utils.KEYS.connector)
