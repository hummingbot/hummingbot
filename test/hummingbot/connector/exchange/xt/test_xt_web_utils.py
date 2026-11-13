from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor


class XtWebUtilsTests(IsolatedAsyncioTestCase):
    def test_urls(self):
        self.assertEqual("https://sapi.xt.com/v4/public/time", web_utils.public_rest_url("/v4/public/time"))
        self.assertEqual("https://sapi.xt.com/v4/order", web_utils.private_rest_url("/v4/order"))

    def test_build_api_factory_uses_native_throttler_and_time_sync(self):
        throttler = web_utils.create_throttler()
        synchronizer = TimeSynchronizer()
        factory = web_utils.build_api_factory(throttler=throttler, time_synchronizer=synchronizer)
        self.assertIs(throttler, factory._throttler)
        self.assertIsInstance(factory._rest_pre_processors[0], TimeSynchronizerRESTPreProcessor)
        self.assertEqual([], web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler)
                         ._rest_pre_processors)
        self.assertIsNotNone(web_utils.build_api_factory())

    @aioresponses()
    async def test_get_current_server_time_unwraps_xt_envelope(self, mock_api):
        mock_api.get(web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL),
                     payload={"rc": 0, "mc": "SUCCESS", "result": {"serverTime": 1700000000123}})
        self.assertEqual(1700000000123, await web_utils.get_current_server_time())

    async def test_factory_time_provider_fetches_from_xt(self):
        with patch.object(web_utils, "get_current_server_time", new=AsyncMock(return_value=1700000000123)) as clock:
            factory = web_utils.build_api_factory()
            pre_processor = factory._rest_pre_processors[0]
            await pre_processor._time_provider()
            clock.assert_awaited_once()

    def test_response_errors_keep_venue_code_for_native_error_handlers(self):
        self.assertEqual({"ok": True}, web_utils.result_from_response({"rc": 0, "result": {"ok": True}}, "test"))
        for response in ("not-json", {"rc": 1, "mc": "AUTH_105"}, {"mc": "SUCCESS"}):
            with self.subTest(response=response), self.assertRaises(IOError):
                web_utils.result_from_response(response, "test")
        self.assertTrue(web_utils.is_time_sync_error_response({"rc": 1, "mc": "AUTH_105"}))
        for response in (None, {"rc": 0, "mc": "AUTH_105"}, {"rc": 1, "mc": "AUTH_103"}):
            self.assertFalse(web_utils.is_time_sync_error_response(response))

    def test_only_documented_rejections_allow_create_failure(self):
        for code in ("ORDER_002", "ORDER_F0101", "AUTH_103", "SYMBOL_005"):
            self.assertTrue(web_utils.is_definitive_order_create_rejection({"rc": 1, "mc": code}))
        for response in (None, {}, {"rc": 1, "mc": "COMMON_002"}, {"rc": 1, "mc": "UNKNOWN"}):
            self.assertFalse(web_utils.is_definitive_order_create_rejection(response))
