import asyncio
import os
import socket
import unittest

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils

from mock import patch
from typing import Awaitable

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import (
    BROKER_ID,
    BinancePerpetualRESTPreProcessor,
)
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

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.get_tracking_nonce")
    def test_get_client_order_id(self, mock_nonce):
        mock_nonce.return_value = int("1" * 16)
        client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]

        result = utils.get_client_order_id("buy", self.trading_pair)

        expected_client_order_id = f"{BROKER_ID}-BCAHT{client_instance_id}{int('1'*16)}"

        self.assertEqual(result, expected_client_order_id)

    def test_rest_url_main_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = path_url = "/TEST_PATH_URL"

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
