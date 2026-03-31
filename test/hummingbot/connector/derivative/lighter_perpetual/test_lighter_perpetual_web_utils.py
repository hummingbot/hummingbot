import importlib
import sys
import types
import unittest


def _ensure_limit_order_stub():
    module_name = "hummingbot.core.data_type.limit_order"
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class LimitOrder:
        pass

    stub_module.LimitOrder = LimitOrder
    sys.modules[module_name] = stub_module


try:
    from hummingbot.connector.derivative.lighter_perpetual import (
        lighter_perpetual_constants as CONSTANTS,
        lighter_perpetual_web_utils as web_utils,
    )
except ModuleNotFoundError as import_error:
    if import_error.name != "hummingbot.core.data_type.limit_order":
        raise
    _ensure_limit_order_stub()
    CONSTANTS = importlib.import_module("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants")
    web_utils = importlib.import_module("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_web_utils")


class LighterPerpetualWebUtilsTests(unittest.TestCase):

    def test_public_rest_url(self):
        self.assertEqual(
            f"{CONSTANTS.REST_URL}/orderBooks",
            web_utils.public_rest_url("/orderBooks", domain=CONSTANTS.DEFAULT_DOMAIN),
        )

    def test_public_rest_url_mainnet(self):
        self.assertEqual(
            f"{CONSTANTS.REST_URL}/orderBooks",
            web_utils.public_rest_url("/orderBooks", domain=CONSTANTS.DEFAULT_DOMAIN),
        )

    def test_public_rest_url_testnet(self):
        self.assertEqual(
            f"{CONSTANTS.TESTNET_REST_URL}/orderBooks",
            web_utils.public_rest_url("/orderBooks", domain=CONSTANTS.TESTNET_DOMAIN),
        )

    def test_private_rest_url(self):
        self.assertEqual(
            f"{CONSTANTS.REST_URL}/account",
            web_utils.private_rest_url("/account", domain=CONSTANTS.DEFAULT_DOMAIN),
        )

    def test_wss_url(self):
        self.assertEqual(CONSTANTS.WSS_URL, web_utils.wss_url(domain=CONSTANTS.DEFAULT_DOMAIN))
        self.assertEqual(CONSTANTS.TESTNET_WSS_URL, web_utils.wss_url(domain=CONSTANTS.TESTNET_DOMAIN))
