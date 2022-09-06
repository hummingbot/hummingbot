import unittest

import hummingbot.connector.exchange.foxbit.foxbit_constants as CONSTANTS
from hummingbot.connector.exchange.foxbit import foxbit_web_utils as web_utils


class FoxbitUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "TEST_PATH"
        domain = "com.br"
        expected_url = f"https://{CONSTANTS.REST_URL}/rest/{CONSTANTS.PUBLIC_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "TEST_PATH"
        domain = "com.br"
        expected_url = f"https://{CONSTANTS.REST_URL}/rest/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))

    def test_rest_endpoint_url(self):
        path_url = "TEST_PATH"
        domain = "com.br"
        expected_url = f"/rest/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        public_url = web_utils.public_rest_url(path_url, domain)
        private_url = web_utils.private_rest_url(path_url, domain)
        self.assertEqual(expected_url, web_utils.rest_endpoint_url(public_url))
        self.assertEqual(expected_url, web_utils.rest_endpoint_url(private_url))
