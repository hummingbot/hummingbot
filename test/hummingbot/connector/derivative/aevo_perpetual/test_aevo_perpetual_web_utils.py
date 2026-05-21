import unittest
from decimal import Decimal

from hummingbot.connector.derivative.aevo_perpetual import (
    aevo_perpetual_constants as CONSTANTS,
    aevo_perpetual_web_utils as web_utils,
)


class AevoPerpetualWebUtilsTest(unittest.TestCase):
    def test_public_rest_url_mainnet(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL)
        self.assertEqual("https://api.aevo.xyz/time", url)

    def test_public_rest_url_testnet(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, domain="aevo_perpetual_testnet")
        self.assertEqual("https://api-testnet.aevo.xyz/time", url)

    def test_wss_url(self):
        self.assertEqual("wss://ws.aevo.xyz", web_utils.wss_url())
        self.assertEqual("wss://ws-testnet.aevo.xyz", web_utils.wss_url(domain="aevo_perpetual_testnet"))

    def test_decimal_to_int(self):
        value = Decimal("1.234567")
        self.assertEqual(1234567, web_utils.decimal_to_int(value))
