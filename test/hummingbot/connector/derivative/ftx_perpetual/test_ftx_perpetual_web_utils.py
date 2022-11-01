from unittest import TestCase

from hummingbot.connector.derivative.ftx_perpetual import (
    ftx_perpetual_constants as CONSTANTS,
    ftx_perpetual_web_utils as web_utils,
)


class WebUtilsTests(TestCase):
    def test_public_rest_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.FTX_MARKETS_PATH)
        self.assertEqual('https://ftx.com/api/markets', url)
