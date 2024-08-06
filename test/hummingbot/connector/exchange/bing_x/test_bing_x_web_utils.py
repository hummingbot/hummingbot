from unittest import TestCase

from hummingbot.connector.exchange.bing_x import bing_x_constants as CONSTANTS, bing_x_web_utils as web_utils


class WebUtilsTests(TestCase):
    def test_rest_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.LAST_TRADED_PRICE_PATH, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual('https://open-api.bingx.com/openApi/spot/v1/ticker/24hr', url)
