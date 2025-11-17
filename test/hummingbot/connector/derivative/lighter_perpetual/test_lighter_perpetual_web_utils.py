import unittest

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterPerpetualWebUtilsTest(unittest.TestCase):
    def test_public_rest_url_uses_domain(self):
        url = web_utils.public_rest_url("/api/v1/orderBooks", CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual("https://mainnet.zklighter.elliot.ai/api/v1/orderBooks", url)

    def test_private_rest_url_uses_domain(self):
        url = web_utils.private_rest_url("/api/v1/orders", CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual("https://testnet.zklighter.elliot.ai/api/v1/orders", url)

    def test_wss_url_uses_domain(self):
        url = web_utils.wss_url(CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual("wss://mainnet.zklighter.elliot.ai/stream", url)

    def test_create_throttler_returns_async_throttler(self):
        throttler = web_utils.create_throttler()
        self.assertIsInstance(throttler, AsyncThrottler)

    def test_build_api_factory_returns_factory_with_throttler(self):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        api_factory = web_utils.build_api_factory(throttler=throttler)

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIs(api_factory._throttler, throttler)
