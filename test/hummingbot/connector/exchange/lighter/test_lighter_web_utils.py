import unittest

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterWebUtilsTests(unittest.TestCase):
    def test_public_rest_url(self):
        self.assertEqual(
            f"{CONSTANTS.REST_URL}{CONSTANTS.EXCHANGE_INFO_PATH_URL}",
            web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL),
        )

    def test_private_rest_url(self):
        self.assertEqual(
            f"{CONSTANTS.REST_URL}{CONSTANTS.GET_ACCOUNT_INFO_PATH_URL}",
            web_utils.private_rest_url(CONSTANTS.GET_ACCOUNT_INFO_PATH_URL),
        )

    def test_wss_url(self):
        self.assertEqual(CONSTANTS.WSS_URL, web_utils.wss_url())

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)
