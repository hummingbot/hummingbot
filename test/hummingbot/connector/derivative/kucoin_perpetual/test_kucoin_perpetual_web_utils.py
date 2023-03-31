from unittest import TestCase

from hummingbot.connector.derivative.kucoin_perpetual import kucoin_perpetual_web_utils as web_utils


class WebUtilsTests(TestCase):
    def test_get_rest_url_for_endpoint(self):
        endpoint = "testEndpoint"

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="kucoin_perpetual_main")
        self.assertEqual("https://api-futures.kucoin.com/testEndpoint", url)

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="kucoin_perpetual_testnet")
        self.assertEqual("https://api-sandbox-futures.kucoin.com/testEndpoint", url)
