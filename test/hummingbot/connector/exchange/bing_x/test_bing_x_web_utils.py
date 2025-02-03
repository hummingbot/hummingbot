from unittest import TestCase

from hummingbot.connector.exchange.bing_x import bing_x_constants as CONSTANTS, bing_x_web_utils as web_utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class WebUtilsTests(TestCase):
    def __init__(self, methodName: str = "runTest"):
        super().__init__(methodName)
        self.throttler = None

    def test_rest_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.LAST_TRADED_PRICE_PATH, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual('https://open-api.bingx.com/openApi/spot/v1/ticker/24hr', url)

    def test_wss_url(self):
        url = web_utils.wss_url(path_url="", domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual('wss://open-api-ws.bingx.com/market', url)

    def test_create_throttler(self):
        throttler = web_utils.create_throttler()
        self.assertIsInstance(throttler, AsyncThrottler)
        self.assertEqual(len(throttler._rate_limits), len(CONSTANTS.RATE_LIMITS))

    def test_build_api_factory(self):
        throttler = web_utils.create_throttler()
        api_factory = web_utils.build_api_factory(throttler=throttler)
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertEqual(api_factory._throttler, throttler)

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler=self.throttler)
        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertEqual(api_factory._throttler, self.throttler)
        self.assertEqual(len(api_factory._rest_pre_processors), 0)
