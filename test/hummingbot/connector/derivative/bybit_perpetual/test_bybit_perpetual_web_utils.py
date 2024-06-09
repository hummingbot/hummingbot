import unittest

from hummingbot.connector.derivative.bybit_perpetual import (
    bybit_perpetual_constants as CONSTANTS,
    bybit_perpetual_web_utils as web_utils,
)


class BybitPerpetualWebUtilsTest(unittest.TestCase):
    def test_get_rest_url_for_endpoint(self):
        endpoint = {
            "linear": "testEndpoint/linear",
            "non_linear": "testEndpoint/non_linear"
        }
        linear_pair = "ETH-USDT"
        non_linear_pair = "ETH-BTC"

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="bybit_perpetual_main")
        self.assertEqual("https://api.bybit.com/testEndpoint/linear", url)

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="bybit_perpetual_testnet")
        self.assertEqual("https://api-testnet.bybit.com/testEndpoint/linear", url)

        url = web_utils.get_rest_url_for_endpoint(
            endpoint, trading_pair=linear_pair, domain="bybit_perpetual_main"
        )
        self.assertEqual("https://api.bybit.com/testEndpoint/linear", url)

        url = web_utils.get_rest_url_for_endpoint(
            endpoint, trading_pair=linear_pair, domain="bybit_perpetual_testnet"
        )
        self.assertEqual("https://api-testnet.bybit.com/testEndpoint/linear", url)

        url = web_utils.get_rest_url_for_endpoint(
            endpoint, trading_pair=non_linear_pair, domain="bybit_perpetual_main"
        )
        self.assertEqual("https://api.bybit.com/testEndpoint/non_linear", url)

        url = web_utils.get_rest_url_for_endpoint(
            endpoint, trading_pair=non_linear_pair, domain="bybit_perpetual_testnet"
        )
        self.assertEqual("https://api-testnet.bybit.com/testEndpoint/non_linear", url)

    def test_wss_linear_public_url(self):
        url = web_utils.wss_linear_public_url(None)
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URL_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_linear_public_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URL_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_linear_public_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URL_LINEAR.get("bybit_perpetual_testnet"), url)

    def test_wss_linear_private_url(self):
        url = web_utils.wss_linear_private_url(None)
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URL_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_linear_private_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URL_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_linear_private_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URL_LINEAR.get("bybit_perpetual_testnet"), url)

    def test_wss_non_linear_public_url(self):
        url = web_utils.wss_non_linear_public_url(None)
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URL_NON_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_non_linear_public_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URL_NON_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_non_linear_public_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URL_NON_LINEAR.get("bybit_perpetual_testnet"), url)

    def test_wss_non_linear_private_url(self):
        url = web_utils.wss_non_linear_private_url(None)
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URL_NON_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_non_linear_private_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URL_NON_LINEAR.get("bybit_perpetual_main"), url)

        url = web_utils.wss_non_linear_private_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URL_NON_LINEAR.get("bybit_perpetual_testnet"), url)
