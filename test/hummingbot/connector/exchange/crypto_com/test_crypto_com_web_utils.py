import unittest

import hummingbot.connector.exchange.crypto_com.crypto_com_constants as CONSTANTS
from hummingbot.connector.exchange.crypto_com import crypto_com_web_utils as web_utils


class CryptoComUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PUBLIC_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))
