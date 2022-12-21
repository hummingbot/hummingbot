from unittest import TestCase

from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS, ascend_ex_web_utils as web_utils


class AscendExWebUtilsTests(TestCase):
    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.PUBLIC_REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_rest_api_url_private(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.PRIVATE_REST_URL + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url))
