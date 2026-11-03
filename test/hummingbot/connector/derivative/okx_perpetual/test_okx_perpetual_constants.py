import unittest

from hummingbot.connector.derivative.okx_perpetual import okx_perpetual_constants as CONSTANTS


class OKXPerpetualConstantsTest(unittest.TestCase):

    def test_ws_urls_use_the_default_tls_port(self):
        for domain, url in CONSTANTS.WSS_PUBLIC_URLS.items():
            self.assertTrue(url.startswith("wss://"), msg=domain)
            self.assertIn(":443/ws/v5/public", url, msg=domain)
            self.assertNotIn(":8443", url, msg=domain)

        for domain, url in CONSTANTS.WSS_PRIVATE_URLS.items():
            self.assertTrue(url.startswith("wss://"), msg=domain)
            self.assertIn(":443/ws/v5/private", url, msg=domain)
            self.assertNotIn(":8443", url, msg=domain)

        for domain, url in CONSTANTS.WSS_BUSINESS_URLS.items():
            self.assertTrue(url.startswith("wss://"), msg=domain)
            self.assertIn(":443/ws/v5/business", url, msg=domain)
            self.assertNotIn(":8443", url, msg=domain)