import unittest

from hummingbot.connector.derivative.hashkey_perpetual import (
    hashkey_perpetual_constants as CONSTANTS,
    hashkey_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HashkeyPerpetualWebUtilsTest(unittest.TestCase):

    def test_public_rest_url(self):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_PATH_URL)
        self.assertEqual("https://api-glb.hashkey.com/quote/v1/depth", url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))
