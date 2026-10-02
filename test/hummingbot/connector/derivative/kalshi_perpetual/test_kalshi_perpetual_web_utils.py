import time
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils import KalshiPerpetualRESTPreProcessor
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KalshiPerpetualWebUtilsTests(IsolatedAsyncioWrapperTestCase):

    async def test_rest_pre_processor_sets_json_content_type(self):
        for method in (RESTMethod.GET, RESTMethod.POST, RESTMethod.PUT, RESTMethod.DELETE):
            request = RESTRequest(method=method, url="/TEST_URL")

            result_request = await KalshiPerpetualRESTPreProcessor().pre_process(request)

            self.assertEqual("application/json", result_request.headers["Content-Type"])

    async def test_rest_pre_processor_keeps_existing_headers(self):
        request = RESTRequest(method=RESTMethod.GET, url="/TEST_URL", headers={"KALSHI-ACCESS-KEY": "key"})

        result_request = await KalshiPerpetualRESTPreProcessor().pre_process(request)

        self.assertEqual("key", result_request.headers["KALSHI-ACCESS-KEY"])
        self.assertEqual("application/json", result_request.headers["Content-Type"])

    def test_public_rest_url(self):
        self.assertEqual(
            "https://external-api.kalshi.com/trade-api/v2/margin/exchange/status",
            web_utils.public_rest_url(path_url="/margin/exchange/status"),
        )

    def test_private_rest_url_uses_same_base_url_as_public(self):
        path_url = "/margin/portfolio/balance"

        self.assertEqual(
            f"{CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN]}{path_url}",
            web_utils.private_rest_url(path_url=path_url, domain=CONSTANTS.DEFAULT_DOMAIN),
        )
        self.assertEqual(web_utils.public_rest_url(path_url), web_utils.private_rest_url(path_url))

    def test_rest_url_unknown_domain_raises(self):
        with self.assertRaises(KeyError):
            web_utils.public_rest_url(path_url="/margin/exchange/status", domain="kalshi_perpetual_demo")

    def test_wss_url(self):
        self.assertEqual(
            "wss://external-api-margin-ws.kalshi.com/trade-api/ws/v2/margin",
            web_utils.wss_url(domain=CONSTANTS.DEFAULT_DOMAIN),
        )

    def test_is_exchange_information_valid(self):
        self.assertTrue(web_utils.is_exchange_information_valid({"ticker": "KXBTCPERP", "status": "active"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"ticker": "KXGOLDPERP", "status": "inactive"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"ticker": "KXBTCPERP", "status": "closed"}))
        self.assertFalse(web_utils.is_exchange_information_valid({"ticker": "BTC-USD", "status": "active"}))

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)
        self.assertEqual(1, len(api_factory._rest_pre_processors))
        self.assertIsInstance(api_factory._rest_pre_processors[0], KalshiPerpetualRESTPreProcessor)

    def test_build_api_factory_with_auth_and_throttler(self):
        auth = MagicMock(spec=AuthBase)
        throttler = AsyncThrottler(rate_limits=[])

        api_factory = web_utils.build_api_factory(throttler=throttler, auth=auth)

        self.assertIs(auth, api_factory._auth)
        self.assertIs(throttler, api_factory._throttler)

    def test_create_throttler(self):
        self.assertIsInstance(web_utils.create_throttler(), AsyncThrottler)

    @patch("hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils.time.time")
    async def test_get_current_server_time_returns_local_time_in_milliseconds(self, time_mock):
        time_mock.return_value = 1_789_035_399.5

        server_time = await web_utils.get_current_server_time()

        self.assertEqual(1_789_035_399_500, server_time)

    async def test_time_synchronizer_stays_on_local_time(self):
        # Regression guard: returning seconds instead of milliseconds would pull the synchronized time to ~0.
        time_synchronizer = TimeSynchronizer()

        await time_synchronizer.update_server_time_offset_with_time_provider(web_utils.get_current_server_time())

        self.assertLess(abs(time_synchronizer.time() - time.time()), 1)
