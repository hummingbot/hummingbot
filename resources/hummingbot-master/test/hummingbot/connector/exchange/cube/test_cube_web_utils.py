import unittest

import hummingbot.connector.exchange.cube.cube_constants as CONSTANTS
from hummingbot.connector.exchange.cube import cube_web_utils as web_utils


class CubeUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "live"
        expected_url = CONSTANTS.REST_URL.get(domain) + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "live"
        expected_url = CONSTANTS.REST_URL.get(domain) + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))
