import asyncio
import unittest
from typing import Awaitable

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_web_utils import PhemexPerpetualRESTPreProcessor
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class PhemexPerpetualWebUtilsUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.pre_processor = PhemexPerpetualRESTPreProcessor()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_phemex_perpetual_rest_pre_processor_non_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET,
            url="/TEST_URL",
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/x-www-form-urlencoded")

    def test_phemex_perpetual_rest_pre_processor_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST,
            url="/TEST_URL",
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")

    def test_rest_url_main_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.BASE_URLS[CONSTANTS.DEFAULT_DOMAIN]}{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_rest_url_testnet_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.BASE_URLS[CONSTANTS.TESTNET_DOMAIN]}{path_url}"
        self.assertEqual(
            expected_url, web_utils.public_rest_url(path_url=path_url, domain=CONSTANTS.TESTNET_DOMAIN)
        )

    def test_wss_url_main_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.WSS_URLS[CONSTANTS.DEFAULT_DOMAIN]}{endpoint}"
        self.assertEqual(expected_url, web_utils.wss_url(endpoint=endpoint))

    def test_wss_url_testnet_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.WSS_URLS[CONSTANTS.TESTNET_DOMAIN]}{endpoint}"
        self.assertEqual(expected_url, web_utils.wss_url(endpoint=endpoint, domain=CONSTANTS.TESTNET_DOMAIN))

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))
