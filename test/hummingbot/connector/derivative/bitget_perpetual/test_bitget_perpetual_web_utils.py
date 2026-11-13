import json
import time
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict
from unittest.mock import MagicMock

from aioresponses import aioresponses

from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_constants as CONSTANTS,
    bitget_perpetual_web_utils as web_utils,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitgetPerpetualWebUtilsTests(IsolatedAsyncioWrapperTestCase):

    @staticmethod
    def _server_time_response(server_time_ms: int) -> Dict[str, Any]:
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": server_time_ms,
            "data": {"serverTime": str(server_time_ms)},
        }

    def test_public_rest_url(self):
        self.assertEqual(
            "https://api.bitget.com/api/v3/market/time",
            web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT),
        )

    def test_private_rest_url_uses_the_public_base_url(self):
        path_url = CONSTANTS.PLACE_ORDER_ENDPOINT

        self.assertEqual(
            "https://api.bitget.com/api/v3/trade/place-order",
            web_utils.private_rest_url(path_url=path_url, domain=CONSTANTS.DEFAULT_DOMAIN),
        )
        self.assertEqual(web_utils.public_rest_url(path_url), web_utils.private_rest_url(path_url))

    def test_rest_url_unknown_domain_raises(self):
        with self.assertRaises(KeyError):
            web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT, domain="bitget.com")
        with self.assertRaises(KeyError):
            web_utils.private_rest_url(path_url=CONSTANTS.PLACE_ORDER_ENDPOINT, domain="bitget.com")

    def test_ws_urls(self):
        self.assertEqual("wss://ws.bitget.com/v3/ws/public", web_utils.public_ws_url())
        self.assertEqual("wss://ws.bitget.com/v3/ws/private", web_utils.private_ws_url())

    def test_ws_url_unknown_domain_raises(self):
        with self.assertRaises(KeyError):
            web_utils.public_ws_url(domain="bitget.com")
        with self.assertRaises(KeyError):
            web_utils.private_ws_url(domain="bitget.com")

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)
        self.assertEqual(1, len(api_factory._rest_pre_processors))
        self.assertIsInstance(api_factory._rest_pre_processors[0], TimeSynchronizerRESTPreProcessor)

    def test_build_api_factory_with_auth_and_throttler(self):
        auth = MagicMock(spec=AuthBase)
        throttler = AsyncThrottler(rate_limits=[])

        api_factory = web_utils.build_api_factory(throttler=throttler, auth=auth)

        self.assertIs(auth, api_factory._auth)
        self.assertIs(throttler, api_factory._throttler)

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(
            throttler=AsyncThrottler(rate_limits=[])
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertEqual(0, len(api_factory._rest_pre_processors))

    def test_create_throttler(self):
        throttler = web_utils.create_throttler()

        self.assertIsInstance(throttler, AsyncThrottler)
        self.assertEqual(
            {rate_limit.limit_id for rate_limit in CONSTANTS.RATE_LIMITS},
            set(throttler._id_to_limit_map.keys()),
        )

    @aioresponses()
    async def test_get_current_server_time(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT)
        mock_api.get(url, body=json.dumps(self._server_time_response(1688008631614)))

        server_time = await web_utils.get_current_server_time()

        self.assertEqual(1688008631614, server_time)

    @aioresponses()
    async def test_time_synchronizer_offset_follows_the_server_clock(self, mock_api):
        # The server runs 5 s ahead; reading its milliseconds as seconds would put the offset off by ~1000x.
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT)
        mock_api.get(url, body=json.dumps(self._server_time_response(int((time.time() + 5) * 1e3))))
        time_synchronizer = TimeSynchronizer()

        await time_synchronizer.update_server_time_offset_with_time_provider(web_utils.get_current_server_time())

        self.assertAlmostEqual(time.time() + 5, time_synchronizer.time(), delta=1)

    @aioresponses()
    async def test_rest_pre_processor_synchronizes_time_before_the_first_request(self, mock_api):
        time_url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT)
        mock_api.get(time_url, body=json.dumps(self._server_time_response(int((time.time() + 5) * 1e3))))
        ticker_url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_TICKER_ENDPOINT)
        mock_api.get(ticker_url, body=json.dumps({"code": "00000", "msg": "success", "data": []}))
        time_synchronizer = TimeSynchronizer()
        api_factory = web_utils.build_api_factory(time_synchronizer=time_synchronizer)
        rest_assistant = await api_factory.get_rest_assistant()

        await rest_assistant.execute_request(
            url=ticker_url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.PUBLIC_TICKER_ENDPOINT,
        )

        self.assertEqual(1, len(time_synchronizer._time_offset_ms))
        self.assertAlmostEqual(time.time() + 5, time_synchronizer.time(), delta=1)
