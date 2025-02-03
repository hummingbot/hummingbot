import unittest

from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS, derive_web_utils as web_utils
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DeriveWebUtilsTest(unittest.TestCase):

    def test_public_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_PATH_URL)
        self.assertEqual("https://api.lyra.finance/public/get_ticker", url)

    def test_private_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_PATH_URL)
        self.assertEqual("https://api.lyra.finance/public/get_ticker", url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))
