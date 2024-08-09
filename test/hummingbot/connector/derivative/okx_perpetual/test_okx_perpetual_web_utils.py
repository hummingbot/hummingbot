import asyncio
import json
import re
import unittest
from typing import Awaitable

from aioresponses import aioresponses

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

    def test_wss_linear_public_url(self):
        url = web_utils.wss_linear_public_url(None)
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URLS.get("okx_perpetual"), url)

        url = web_utils.wss_linear_public_url("okx_perpetual")
        self.assertEqual(CONSTANTS.WSS_PUBLIC_URLS.get("okx_perpetual"), url)

    def test_wss_linear_private_url(self):
        url = web_utils.wss_linear_private_url(None)
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URLS.get("okx_perpetual"), url)

        url = web_utils.wss_linear_private_url("okx_perpetual")
        self.assertEqual(CONSTANTS.WSS_PRIVATE_URLS.get("okx_perpetual"), url)

    def test_rest_private_pair_specific_rate_limits(self):
        trading_pairs = ["COINALPHA-HBOT"]
        rate_limits = web_utils._build_private_pair_specific_rate_limits(trading_pairs)
        self.assertEqual(3, len(rate_limits))

    @staticmethod
    def push_data_mock_message():
        return {
            "arg": {
                "channel": "some-channel",
                "instId": "COINALPHA-HBOT-SWAP"
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": "COINALPHA-HBOT-SWAP",
                    "someParam": "someValue"
                }
            ]
        }

    @staticmethod
    def failure_response_example_mock_message():
        return {
            "event": "error",
            "code": "9999",
            "msg": "Some error message",
            "connId": "a4d3ae55"
        }

    @staticmethod
    def successful_response_mock_message():
        return {
            "event": "subscribe",
            "arg": {
                "channel": "some-channel",
                "instId": "COINALPHA-HBOT-SWAP"
            },
            "connId": "a4d3ae55"
        }

    def test_payload_from_message(self):
        payload = web_utils.payload_from_message(self.push_data_mock_message())
        self.assertEqual(payload, [
            {
                "instType": "SWAP",
                "instId": "COINALPHA-HBOT-SWAP",
                "someParam": "someValue"
            }
        ])
        self.assertIsInstance(payload, list)

    def test_endpoint_from_message(self):
        successful_subscription_endpoint = web_utils.endpoint_from_message(self.push_data_mock_message())
        self.assertEqual(successful_subscription_endpoint, "some-channel")
        failure_response_endpoint = web_utils.endpoint_from_message(self.failure_response_example_mock_message())
        self.assertEqual(failure_response_endpoint, "error")
        other_response = "non-dict-response"
        self.assertIsNone(web_utils.endpoint_from_message(other_response))

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

    @aioresponses()
    def test_get_current_server_time(self, mock_api):
        response = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "ts": "1597026383085"
                }
            ]
        }
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_SERVER_TIME,
                                                  domain=CONSTANTS.DEFAULT_DOMAIN)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps(response))

        response = self.async_run_with_timeout(web_utils.get_current_server_time())
        self.assertEqual(response, 1597026383085)
