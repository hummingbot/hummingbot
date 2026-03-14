from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS


class GRVTPerpetualWebUtilsTests(TestCase):
    def test_public_rest_url(self):
        url = web_utils.public_rest_url("test/path", "grvt_perpetual")
        self.assertEqual("https://api.grvt.io/test/path", url)

    def test_public_rest_url_testnet(self):
        url = web_utils.public_rest_url("test/path", "grvt_perpetual_testnet")
        self.assertEqual("https://api-testnet.grvt.io/test/path", url)

    def test_private_rest_url(self):
        url = web_utils.private_rest_url("test/path", "grvt_perpetual")
        self.assertEqual("https://api.grvt.io/test/path", url)

    def test_private_rest_url_testnet(self):
        url = web_utils.private_rest_url("test/path", "grvt_perpetual_testnet")
        self.assertEqual("https://api-testnet.grvt.io/test/path", url)

    def test_wss_url(self):
        url = web_utils.wss_url("ws", "grvt_perpetual")
        self.assertEqual("wss://ws.grvt.io/ws", url)

    def test_wss_url_testnet(self):
        url = web_utils.wss_url("ws", "grvt_perpetual_testnet")
        self.assertEqual("wss://ws-testnet.grvt.io/ws", url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()
        self.assertIsNotNone(api_factory)

    def test_create_throttler(self):
        throttler = web_utils.create_throttler()
        self.assertIsNotNone(throttler)

    def test_is_exchange_information_valid_true(self):
        rule = {
            "status": "TRADING",
            "contractType": "PERPETUAL",
        }
        self.assertTrue(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_false_status(self):
        rule = {
            "status": "BREAK",
            "contractType": "PERPETUAL",
        }
        self.assertFalse(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_false_contract_type(self):
        rule = {
            "status": "TRADING",
            "contractType": "OPTION",
        }
        self.assertFalse(web_utils.is_exchange_information_valid(rule))
