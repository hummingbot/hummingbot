import unittest

from kuru_sdk_py.config_defaults import (
    DEFAULT_KURU_API_URL as SDK_DEFAULT_KURU_API_URL,
    DEFAULT_KURU_WS_URL as SDK_DEFAULT_KURU_WS_URL,
    DEFAULT_RPC_URL as SDK_DEFAULT_RPC_URL,
    DEFAULT_RPC_WS_URL as SDK_DEFAULT_RPC_WS_URL,
)

from hummingbot.connector.exchange.kuru import kuru_constants as CONSTANTS


class KuruConstantsTest(unittest.TestCase):

    def test_connector_re_exports_sdk_default_urls(self):
        self.assertEqual(SDK_DEFAULT_RPC_URL, CONSTANTS.DEFAULT_RPC_URL)
        self.assertEqual(SDK_DEFAULT_RPC_WS_URL, CONSTANTS.DEFAULT_RPC_WS_URL)
        self.assertEqual(SDK_DEFAULT_KURU_WS_URL, CONSTANTS.DEFAULT_KURU_WS_URL)
        self.assertEqual(SDK_DEFAULT_KURU_API_URL, CONSTANTS.DEFAULT_KURU_API_URL)
