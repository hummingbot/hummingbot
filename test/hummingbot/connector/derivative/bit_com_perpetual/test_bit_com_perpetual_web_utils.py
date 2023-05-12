import unittest

from hummingbot.connector.derivative.bit_com_perpetual import (
    bit_com_perpetual_constants as CONSTANTS,
    bit_com_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitComPerpetualWebUtilsTest(unittest.TestCase):

    def test_public_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL)
        self.assertEqual("https://api.bit.com/linear/v1/orderbooks", url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))
