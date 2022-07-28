import unittest

from hummingbot.core.gateway.utils import unwrap_token_symbol


class GatewayUtilsTest(unittest.TestCase):
    def test_unwrap_token_symbols(self):
        self.assertEqual("ETH", unwrap_token_symbol("WETH"))
        self.assertEqual("ETH", unwrap_token_symbol("WETH.e"))
        self.assertEqual("AVAX", unwrap_token_symbol("WAVAX"))
        self.assertEqual("DAI", unwrap_token_symbol("DAI.e"))
        self.assertEqual("DAI", unwrap_token_symbol("DAI.E"))
        self.assertEqual("WAVE", unwrap_token_symbol("WAVE"))
        self.assertEqual("stETH", unwrap_token_symbol("wstETH"))
