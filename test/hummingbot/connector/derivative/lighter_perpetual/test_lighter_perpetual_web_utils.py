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


_ensure_limit_order_stub()


def _load_web_utils_module():
    from hummingbot.connector.derivative.lighter_perpetual import (
        lighter_perpetual_constants as constants,
        lighter_perpetual_web_utils as web_utils,
    )

    return constants, web_utils


class LighterPerpetualWebUtilsTests(unittest.TestCase):

    def test_public_rest_url(self):
        constants, web_utils = _load_web_utils_module()
        self.assertEqual(
            f"{constants.REST_URL}/orderBooks",
            web_utils.public_rest_url("/orderBooks", domain=constants.DEFAULT_DOMAIN),
        )

    def test_public_rest_url_mainnet(self):
        constants, web_utils = _load_web_utils_module()
        self.assertEqual(
            f"{constants.REST_URL}/orderBooks",
            web_utils.public_rest_url("/orderBooks", domain=constants.DEFAULT_DOMAIN),
        )

    def test_public_rest_url_testnet(self):
        constants, web_utils = _load_web_utils_module()
        self.assertEqual(
            f"{constants.TESTNET_REST_URL}/orderBooks",
            web_utils.public_rest_url("/orderBooks", domain=constants.TESTNET_DOMAIN),
        )

    def test_private_rest_url(self):
        constants, web_utils = _load_web_utils_module()
        self.assertEqual(
            f"{constants.REST_URL}/account",
            web_utils.private_rest_url("/account", domain=constants.DEFAULT_DOMAIN),
        )

    def test_wss_url(self):
        constants, web_utils = _load_web_utils_module()
        self.assertEqual(constants.WSS_URL, web_utils.wss_url(domain=constants.DEFAULT_DOMAIN))
        self.assertEqual(constants.TESTNET_WSS_URL, web_utils.wss_url(domain=constants.TESTNET_DOMAIN))

    def test_tier_2_rate_limits_include_exchange_info(self):
        constants, _ = _load_web_utils_module()
        tier_2_limit_ids = {limit.limit_id for limit in constants.RATE_LIMITS_TIER_2}
        self.assertIn(constants.EXCHANGE_INFO_PATH_URL, tier_2_limit_ids)
