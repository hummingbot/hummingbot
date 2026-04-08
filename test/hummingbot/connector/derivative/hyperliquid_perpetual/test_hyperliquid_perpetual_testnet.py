import unittest

from hummingbot.connector.derivative.hyperliquid_perpetual import hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
    HyperliquidPerpetualDerivative,
)


class HyperliquidPerpetualTestnetTests(unittest.TestCase):
    def test_testnet_connector_disables_hip3_market_hydration(self):
        connector = HyperliquidPerpetualDerivative(
            hyperliquid_perpetual_secret_key="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",
            hyperliquid_perpetual_mode="arb_wallet",
            hyperliquid_perpetual_address="someAddress",
            use_vault=False,
            trading_pairs=["BTC-USD"],
            domain=CONSTANTS.TESTNET_DOMAIN,
        )

        self.assertFalse(connector._enable_hip3_markets)
