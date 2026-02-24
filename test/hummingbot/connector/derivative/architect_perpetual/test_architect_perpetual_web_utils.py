import unittest

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils


class ArchitectPerpetualWebUtilsTests(unittest.TestCase):

    def test_public_rest_url_uses_default(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_URL, domain=CONSTANTS.DOMAIN)
        self.assertEqual(f"{CONSTANTS.DEFAULT_REST_BASE_URL}{CONSTANTS.PING_URL}", url)

    def test_public_ws_url_uses_default(self):
        url = web_utils.public_ws_url(domain=CONSTANTS.DOMAIN)
        self.assertEqual(f"{CONSTANTS.DEFAULT_WSS_BASE_URL}{CONSTANTS.PUBLIC_WS_PATH}", url)

    def test_domain_can_be_full_url(self):
        url = web_utils.public_rest_url("/x", domain="https://example.com/")
        self.assertEqual("https://example.com/x", url)
