import asyncio
import unittest
from typing import Awaitable

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_web_utils import (
    BitmartPerpetualRESTPreProcessor,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
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

    def test_rest_url_main_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.PERPETUAL_BASE_URL}{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain=CONSTANTS.DOMAIN))

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
