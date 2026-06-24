import asyncio
import unittest
from typing import Awaitable
from unittest.mock import Mock, patch

from hummingbot.connector.derivative.drift_perpetual import (
    drift_perpetual_constants as CONSTANTS,
    drift_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DriftPerpetualWebUtilsTest(unittest.TestCase):

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_gateway_rest_url(self):
        url = web_utils.gateway_rest_url(CONSTANTS.PATH_MARKETS)
        self.assertEqual(CONSTANTS.DRIFT_GATEWAY_REST_URL + CONSTANTS.PATH_MARKETS, url)
        # Self-hosted gateway is plain-HTTP loopback, versioned path.
        self.assertTrue(url.startswith("http://"))
        self.assertTrue(url.endswith("/markets"))

    def test_dlob_rest_url(self):
        url = web_utils.dlob_rest_url(CONSTANTS.PATH_DLOB_L2)
        self.assertEqual("https://dlob.drift.trade/l2", url)

    def test_data_api_url(self):
        url = web_utils.data_api_url("/market/SOL-PERP/fundingRates")
        self.assertEqual("https://data.api.drift.trade/market/SOL-PERP/fundingRates", url)

    @patch("hummingbot.connector.derivative.drift_perpetual.drift_perpetual_web_utils"
           ".create_throttler", return_value=Mock())
    def test_build_api_factory(self, mock_create_throttler):
        throttler = web_utils.create_throttler()
        api_factory = web_utils.build_api_factory(throttler)

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        # Drift gateway is unauthenticated from the connector's side
        # (the gateway signs); the factory must carry no auth.
        self.assertIsNone(api_factory._auth)

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    def test_build_api_factory_without_time_synchronizer_pre_processor(self, mock_factory):
        throttler = Mock()
        web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler)
        mock_factory.assert_called_once_with(throttler=throttler)

    @patch("hummingbot.connector.derivative.drift_perpetual.drift_perpetual_web_utils.time.time",
           return_value=1715769499.0)
    def test_get_current_server_time_is_local_clock(self, _mock_time):
        # Gateway is co-located with the bot, so server time == local time
        # and the TimeSynchronizer offset is ~0 by construction.
        server_time = self.async_run_with_timeout(web_utils.get_current_server_time())
        self.assertEqual(1715769499.0, server_time)

    def test_is_exchange_information_valid(self):
        self.assertTrue(web_utils.is_exchange_information_valid({"status": "active"}))
        self.assertTrue(web_utils.is_exchange_information_valid({"status": "Initialized"}))
        # Absent status field is treated as tradeable (lenient default).
        self.assertTrue(web_utils.is_exchange_information_valid({}))
        self.assertFalse(web_utils.is_exchange_information_valid({"status": "delisted"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"status": "settlement"}))

    def test_rest_pre_processor_sets_json_headers(self):
        pre = web_utils.DriftPerpetualRESTPreProcessor()
        request = RESTRequest(method=Mock(), url="http://127.0.0.1:8080/v2/markets")
        processed = self.async_run_with_timeout(pre.pre_process(request))
        self.assertEqual("application/json", processed.headers["Accept"])
        self.assertEqual("application/json", processed.headers["Content-Type"])
