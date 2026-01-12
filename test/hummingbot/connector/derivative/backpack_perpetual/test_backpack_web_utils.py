from unittest import TestCase

from hummingbot.connector.derivative.backpack import backpack_web_utils as web_utils


class WebUtilsTests(TestCase):
    def test_get_rest_url_for_endpoint(self):
        endpoint = "testEndpoint"

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="backpack_main")
        self.assertEqual("https://api-futures.backpack.com/testEndpoint", url)
