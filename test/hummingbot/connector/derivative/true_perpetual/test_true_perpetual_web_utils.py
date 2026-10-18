import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.derivative.true_perpetual import (
    true_perpetual_constants as CONSTANTS,
    true_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TruePerpetualWebUtilsTests(IsolatedAsyncioWrapperTestCase):

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return self.local_event_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_rest_urls(self):
        self.assertEqual("https://app.truefinance.ai/api/bot/v1/markets", web_utils.rest_url(CONSTANTS.MARKETS_PATH_URL))
        self.assertEqual(web_utils.rest_url(CONSTANTS.ACCOUNT_PATH_URL), web_utils.private_rest_url(CONSTANTS.ACCOUNT_PATH_URL))
        self.assertEqual(web_utils.rest_url(CONSTANTS.TICKER_PATH_URL), web_utils.public_rest_url(CONSTANTS.TICKER_PATH_URL))
        self.assertEqual("wss://app.truefinance.ai/api/ws/perps", web_utils.wss_url())

    def test_order_path(self):
        self.assertEqual("/orders/42599337", web_utils.order_path("42599337"))

    def test_is_exchange_information_valid(self):
        self.assertTrue(web_utils.is_exchange_information_valid({"active": True, "lotSize": "0.001", "tickSize": "1"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"active": False, "lotSize": "0.001", "tickSize": "1"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"active": True, "lotSize": None, "tickSize": "1"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"active": True, "lotSize": "0.001"}))

    def test_build_api_factory(self):
        factory = web_utils.build_api_factory()
        self.assertIsNotNone(factory._throttler)
        self.assertEqual(2, len(factory._rest_pre_processors))

    async def test_pre_processor_sets_headers(self):
        processor = web_utils.TruePerpetualRESTPreProcessor()
        get_request = await processor.pre_process(RESTRequest(method=RESTMethod.GET, url="https://app.truefinance.ai/x"))
        self.assertEqual("application/json", get_request.headers["Accept"])
        self.assertNotIn("Content-Type", get_request.headers)
        self.assertEqual("hummingbot-true-perpetual", get_request.headers["User-Agent"])
        post_request = await processor.pre_process(RESTRequest(method=RESTMethod.POST, url="https://app.truefinance.ai/x"))
        self.assertEqual("application/json", post_request.headers["Content-Type"])

    @aioresponses()
    async def test_get_current_server_time(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        mock_api.get(url, body=json.dumps({"ok": True, "serverTime": 1700000000123}))
        server_time = await web_utils.get_current_server_time()
        self.assertEqual(1700000000123.0, server_time)
