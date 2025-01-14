import asyncio
import json
import unittest
from typing import Awaitable

from aioresponses import aioresponses

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils import (
    BitmartPerpetualRESTPreProcessor,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitmartPerpetualWebUtilsUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.pre_processor = BitmartPerpetualRESTPreProcessor()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_bitmart_perpetual_rest_pre_processor_non_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET,
            url="/TEST_URL",
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/x-www-form-urlencoded")

    def test_bitmart_perpetual_rest_pre_processor_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST,
            url="/TEST_URL",
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")

    def test_bitmart_perpetual_rest_pre_processor_with_existing_headers(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST,
            url="/TEST_URL",
            headers={"Authorization": "Bearer token"},
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")
        self.assertIn("Authorization", result_request.headers)
        self.assertEqual(result_request.headers["Authorization"], "Bearer token")

    def test_rest_url_main_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.PERPETUAL_BASE_URL}{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain=CONSTANTS.DOMAIN))

    def test_private_rest_url_main_domain(self):
        path_url = "/TEST_PRIVATE_PATH_URL"

        expected_url = f"{CONSTANTS.PERPETUAL_BASE_URL}{path_url}"
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain=CONSTANTS.DOMAIN))

    def test_wss_url_main_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.PERPETUAL_WS_URL}{endpoint}"
        self.assertEqual(expected_url, web_utils.wss_url(endpoint=endpoint, domain=CONSTANTS.DOMAIN))

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertEqual(1, len(api_factory._rest_pre_processors))
        self.assertIsInstance(api_factory._rest_pre_processors[0], BitmartPerpetualRESTPreProcessor)

    @aioresponses()
    def test_get_current_server_time(self, mock_api):
        response = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "server_time": 1527777538000
            }
        }
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, CONSTANTS.DOMAIN)
        mock_api.get(url, body=json.dumps(response))

        response = self.async_run_with_timeout(web_utils.get_current_server_time())
        self.assertEqual(response, 1527777538000)

    def test_is_exchange_information_valid_true(self):
        rule = {"product_type": 1}
        result = web_utils.is_exchange_information_valid(rule)
        self.assertTrue(result)

    def test_is_exchange_information_valid_false(self):
        rule = {"product_type": 2}
        result = web_utils.is_exchange_information_valid(rule)
        self.assertFalse(result)

    def test_is_exchange_information_valid_missing_key(self):
        rule = {}
        with self.assertRaises(KeyError):
            web_utils.is_exchange_information_valid(rule)
