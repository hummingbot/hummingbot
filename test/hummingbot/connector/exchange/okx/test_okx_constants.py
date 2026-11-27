import unittest

from hummingbot.connector.exchange.okx import okx_constants as CONSTANTS


class OKXConstantsTest(unittest.TestCase):

    def test_ws_url_uses_the_default_tls_port(self):
        self.assertEqual("wss://ws.okx.com:443", CONSTANTS.get_ws_url("www"))
        self.assertEqual("wss://wsus.okx.com:443", CONSTANTS.get_ws_url("app"))
        self.assertEqual("wss://wseea.okx.com:443", CONSTANTS.get_ws_url("my"))

    def test_ws_uris_do_not_use_the_retired_port(self):
        self.assertEqual(
            "wss://ws.okx.com:443/ws/v5/public",
            CONSTANTS.get_okx_ws_uri_public("www"),
        )
        self.assertEqual(
            "wss://ws.okx.com:443/ws/v5/private",
            CONSTANTS.get_okx_ws_uri_private("www"),
        )