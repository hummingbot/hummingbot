from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual import grvt_web_utils


class GrvtWebUtilsTests(TestCase):
    def test_public_rest_url(self):
        url = grvt_web_utils.public_rest_url("/v1/instrument")
        self.assertTrue(url.startswith("https://"))
        self.assertIn("/v1/instrument", url)

    def test_ws_url(self):
        self.assertTrue(grvt_web_utils.wss_url().startswith("wss://"))
