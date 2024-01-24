import asyncio
import unittest
from typing import Awaitable

from hummingbot.connector.derivative.okx_perpetual import (
    okx_perpetual_constants as CONSTANTS,
    okx_perpetual_web_utils as web_utils,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class OKXPerpetualWebUtilsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.pre_processor = web_utils.HeadersContentRESTPreProcessor()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_rest_url_for_endpoint(self):
        endpoint = "/testEndpoint"

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="okx_perpetual")
        self.assertEqual("https://www.okx.com/testEndpoint", url)

        url = web_utils.get_rest_url_for_endpoint(endpoint, domain="okx_perpetual_aws")
        self.assertEqual("https://aws.okx.com/testEndpoint", url)

        # url = web_utils.get_rest_url_for_endpoint(endpoint, domain="okx_perpetual_demo")
        # expected_start = "https://www.okx.com/testEndpoint"
        # expected_end = "?brokerId=9999"
        # regex_pattern = f"{re.escape(expected_start)}.*{re.escape(expected_end)}$"
        # self.assertRegex(regex_pattern, url)

    def test_wss_linear_public_url(self):
        url = web_utils.wss_linear_public_url(None)
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URLS.get("okx_perpetual"), url)

        url = web_utils.wss_linear_public_url("okx_perpetual")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URLS.get("okx_perpetual"), url)

        url = web_utils.wss_linear_public_url("okx_perpetual_aws")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URLS.get("okx_perpetual_aws"), url)

        url = web_utils.wss_linear_public_url("okx_perpetual_demo")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URLS.get("okx_perpetual_demo"), url)

    def test_wss_linear_private_url(self):
        url = web_utils.wss_linear_private_url(None)
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URLS.get("okx_perpetual"), url)

        url = web_utils.wss_linear_private_url("okx_perpetual")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URLS.get("okx_perpetual"), url)

        url = web_utils.wss_linear_private_url("okx_perpetual_aws")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URLS.get("okx_perpetual_aws"), url)

        url = web_utils.wss_linear_private_url("okx_perpetual_demo")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URLS.get("okx_perpetual_demo"), url)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))

    def test_get_pair_specific_limit_id(self):
        limit_id = web_utils.get_pair_specific_limit_id("GET",
                                                        "test/endpoint",
                                                        "BTC-USDT")
        self.assertEqual("GET-test/endpoint-BTC-USDT", limit_id)

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(
            throttler=web_utils.create_throttler()
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(1, len(api_factory._rest_pre_processors))

    def test_okx_perpetual_rest_pre_processor_get_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET,
            url="/TEST_URL",
        )
        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")

    def test_okx_perpetual_rest_pre_processor_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST,
            url="/TEST_URL",
        )
        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")
