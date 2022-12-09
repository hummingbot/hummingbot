import unittest

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken import latoken_web_utils as web_utils


class LatokenUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.domain = "com"
        cls.endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[cls.domain]

    def test_public_rest_url(self):
        path_url = "/auth/account"
        expected_url = CONSTANTS.REST_URL.format(self.endpoint, self.domain) + CONSTANTS.REST_API_VERSION + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, self.domain))

    def test_private_rest_url(self):
        path_url = "/auth/account"
        expected_url = CONSTANTS.REST_URL.format(self.endpoint, self.domain) + CONSTANTS.REST_API_VERSION + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, self.domain))
