from unittest import TestCase

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange.xt import xt_utils


class XtUtilsTests(TestCase):
    def setUp(self):
        self.symbol = {"state": "ONLINE", "tradingEnabled": True, "openapiEnabled": True,
                       "orderTypes": ["LIMIT", "MARKET"], "timeInForces": ["GTC", "GTX"]}

    def test_online_trading_enabled_markets_are_discovered(self):
        self.assertTrue(xt_utils.is_exchange_information_valid(self.symbol))
        self.assertTrue(xt_utils.is_exchange_information_valid({"state": "ONLINE", "tradingEnabled": True}))

    def test_capability_metadata_does_not_exclude_active_markets(self):
        for field, values in (
            ("openapiEnabled", (False, None)),
            ("orderTypes", ([], ["MARKET"], False, None)),
            ("timeInForces", ([], ["IOC"], False, None)),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertTrue(xt_utils.is_exchange_information_valid({**self.symbol, field: value}))
            with self.subTest(missing_field=field):
                info = self.symbol.copy()
                info.pop(field)
                self.assertTrue(xt_utils.is_exchange_information_valid(info))
        self.assertTrue(xt_utils.is_exchange_information_valid({
            **self.symbol, "openapiEnabled": False, "orderTypes": [], "timeInForces": [],
        }))

    def test_unavailable_or_invalid_trading_flags_are_excluded(self):
        for field, value in (
            ("state", "OFFLINE"), ("state", None), ("state", True),
            ("tradingEnabled", False), ("tradingEnabled", None),
            ("tradingEnabled", "true"), ("tradingEnabled", "false"),
            ("tradingEnabled", 1), ("tradingEnabled", 0),
        ):
            with self.subTest(field=field, value=value):
                self.assertFalse(xt_utils.is_exchange_information_valid({**self.symbol, field: value}))
        for field in ("state", "tradingEnabled"):
            with self.subTest(missing_field=field):
                info = self.symbol.copy()
                info.pop(field)
                self.assertFalse(xt_utils.is_exchange_information_valid(info))
        self.assertFalse(xt_utils.is_exchange_information_valid({}))

    def test_native_connector_discovery_finds_xt(self):
        setting = AllConnectorSettings.get_connector_settings()["xt"]
        self.assertEqual("xt", setting.name)
        self.assertIsInstance(setting.config_keys, xt_utils.XtConfigMap)

    def test_credentials_are_secure_and_discoverable(self):
        config = xt_utils.XtConfigMap(xt_api_key="key", xt_api_secret="secret")
        self.assertEqual("xt", xt_utils.KEYS.connector)
        self.assertEqual("key", config.xt_api_key.get_secret_value())
        self.assertNotIn("secret", str(config.xt_api_secret))
        self.assertTrue(xt_utils.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)
        for field in ("xt_api_key", "xt_api_secret"):
            self.assertTrue(xt_utils.XtConfigMap.model_fields[field].json_schema_extra["is_connect_key"])
