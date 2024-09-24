import unittest

import hummingbot.connector.exchange.dexalot.dexalot_constants as CONSTANTS
from hummingbot.connector.exchange.dexalot import dexalot_web_utils as web_utils


class DexalotUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))
