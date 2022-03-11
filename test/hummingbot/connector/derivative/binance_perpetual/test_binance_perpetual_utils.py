import asyncio
import unittest
from typing import Awaitable

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils
import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import BinancePerpetualRESTPreProcessor
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BinancePerpetualUtilsUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        cls.pre_processor = BinancePerpetualRESTPreProcessor()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_binance_perpetual_rest_pre_processor_non_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET,
            url="/TEST_URL",
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/x-www-form-urlencoded")

    def test_binance_perpetual_rest_pre_processor_post_request(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST,
            url="/TEST_URL",
        )

        result_request: RESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")

    def test_rest_url_main_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.PERPETUAL_BASE_URL}{CONSTANTS.API_VERSION_V2}{path_url}"
        self.assertEqual(expected_url, utils.rest_url(path_url, api_version=CONSTANTS.API_VERSION_V2))
        self.assertEqual(expected_url, utils.rest_url(path_url, api_version=CONSTANTS.API_VERSION_V2))

    def test_rest_url_testnet_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.TESTNET_BASE_URL}{CONSTANTS.API_VERSION_V2}{path_url}"
        self.assertEqual(
            expected_url, utils.rest_url(path_url=path_url, domain="testnet", api_version=CONSTANTS.API_VERSION_V2)
        )

    def test_wss_url_main_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.PERPETUAL_WS_URL}{endpoint}"
        self.assertEqual(expected_url, utils.wss_url(endpoint=endpoint))

    def test_wss_url_testnet_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.TESTNET_WS_URL}{endpoint}"
        self.assertEqual(expected_url, utils.wss_url(endpoint=endpoint, domain="testnet"))

    def test_build_api_factory(self):
        api_factory = utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(1, len(api_factory._rest_pre_processors))
