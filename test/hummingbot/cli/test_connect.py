import unittest

from hummingbot.cli.commands.connect import _connect_key_fields, _connectable_exchanges, _prompt_text
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.settings import AllConnectorSettings


class ConnectFieldsTest(unittest.TestCase):
    def test_connectable_exchanges_includes_cex_excludes_gateway(self):
        exchanges = _connectable_exchanges()
        self.assertIn("binance", exchanges)
        # gateway/ethereum-wallet connectors are excluded
        self.assertTrue(all("uniswap" not in e for e in exchanges))

    def test_binance_connect_key_fields(self):
        cfg = ClientConfigAdapter(AllConnectorSettings.get_connector_config_keys("binance"))
        fields = _connect_key_fields(cfg)
        attrs = [f.attr for f in fields]
        self.assertIn("binance_api_key", attrs)
        self.assertIn("binance_api_secret", attrs)
        # the connector-name field is not a connect key
        self.assertNotIn("connector", attrs)
        # api credentials are marked secret (hidden prompts / encrypted)
        self.assertTrue(all(f.client_field_data.is_secure for f in fields))

    def test_prompt_text_resolves_callable(self):
        cfg = ClientConfigAdapter(AllConnectorSettings.get_connector_config_keys("binance"))
        field = next(f for f in _connect_key_fields(cfg) if f.attr == "binance_api_key")
        self.assertIn("API key", _prompt_text(field, cfg))


if __name__ == "__main__":
    unittest.main()
