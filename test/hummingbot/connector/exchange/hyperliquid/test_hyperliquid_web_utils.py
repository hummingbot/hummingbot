import unittest

from hummingbot.connector.exchange.hyperliquid import (
    hyperliquid_constants as CONSTANTS,
    hyperliquid_web_utils as web_utils,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HyperliquidWebUtilsTest(unittest.TestCase):

    def test_public_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL)
        self.assertEqual("https://api.hyperliquid.xyz/info", url)

    def test_private_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL)
        self.assertEqual("https://api.hyperliquid.xyz/info", url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))

    def test_order_type_to_tuple(self):
        data = web_utils.order_type_to_tuple({"limit": {"tif": "Gtc"}})
        self.assertEqual((2, 0), data)
        data = web_utils.order_type_to_tuple({"limit": {"tif": "Alo"}})
        self.assertEqual((1, 0), data)
        data = web_utils.order_type_to_tuple({"limit": {"tif": "Ioc"}})
        self.assertEqual((3, 0), data)

        data = web_utils.order_type_to_tuple({"trigger": {"triggerPx": 1200,
                                                          "isMarket": True,
                                                          "tpsl": "tp"}})
        self.assertEqual((4, 1200), data)
        data = web_utils.order_type_to_tuple({"trigger": {"triggerPx": 1200,
                                                          "isMarket": False,
                                                          "tpsl": "tp"}})
        self.assertEqual((5, 1200), data)
        data = web_utils.order_type_to_tuple({"trigger": {"triggerPx": 1200,
                                                          "isMarket": True,
                                                          "tpsl": "sl"}})
        self.assertEqual((6, 1200), data)
        data = web_utils.order_type_to_tuple({"trigger": {"triggerPx": 1200,
                                                          "isMarket": False,
                                                          "tpsl": "sl"}})
        self.assertEqual((7, 1200), data)

    def test_float_to_int_for_hashing(self):
        data = web_utils.float_to_int_for_hashing(0.01)
        self.assertEqual(1000000, data)
