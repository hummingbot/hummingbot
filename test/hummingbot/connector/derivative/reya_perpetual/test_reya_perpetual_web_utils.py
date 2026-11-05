import unittest

from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_web_utils as web_utils,
)


class ReyaPerpetualWebUtilsTests(unittest.TestCase):
    def test_urls_per_domain(self):
        self.assertEqual("https://api.reya.xyz/v2/feeTiers", web_utils.public_rest_url("feeTiers"))
        self.assertEqual("https://api-devnet.reya-cronos.network/v2/feeTiers",
                         web_utils.private_rest_url("feeTiers", CONSTANTS.TESTNET_DOMAIN))
        self.assertEqual("wss://ws.reya.xyz", web_utils.wss_url())
        self.assertEqual("https://api.reya.xyz/api/trading/wallet/0xabc/apiWalletStatus",
                         web_utils.api_wallet_status_url("0xABC"))

    def test_only_trading_rusd_perps_are_valid(self):
        self.assertTrue(web_utils.is_exchange_information_valid({"symbol": "BTCRUSDPERP", "status": "TRADING"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"symbol": "BTCRUSDPERP", "status": "PREOPEN"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"symbol": "WETHRUSD", "status": "TRADING"}))
