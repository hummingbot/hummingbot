import asyncio
from unittest import TestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_web_utils import (
    build_api_factory,
    build_api_factory_without_time_synchronizer_pre_processor,
    create_throttler,
    get_current_server_time,
    private_rest_url,
    public_rest_url,
    wss_url,
)


class GeminiWebUtilsTests(TestCase):

    @staticmethod
    def async_run_with_timeout(coroutine, timeout: float = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_public_rest_url(self):
        url = public_rest_url(CONSTANTS.SYMBOLS_PATH_URL)
        self.assertEqual("https://api.gemini.com/v1/symbols", url)

    def test_private_rest_url(self):
        url = private_rest_url(CONSTANTS.NEW_ORDER_PATH_URL)
        self.assertEqual("https://api.gemini.com/v1/order/new", url)

    def test_wss_url(self):
        url = wss_url()
        self.assertEqual("wss://ws.gemini.com", url)

    def test_create_throttler(self):
        throttler = create_throttler()
        self.assertIsNotNone(throttler)

    def test_build_api_factory(self):
        api_factory = build_api_factory()
        self.assertIsNotNone(api_factory)
        # A time-synchronizer pre-processor should be configured by default
        self.assertEqual(1, len(api_factory._rest_pre_processors))

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=create_throttler())
        self.assertIsNotNone(api_factory)
        self.assertEqual(0, len(api_factory._rest_pre_processors))

    @aioresponses()
    def test_get_current_server_time_parses_date_header(self, mock_api):
        url = public_rest_url(path_url=CONSTANTS.SYMBOLS_PATH_URL)
        mock_api.get(
            url,
            body='["btcusd"]',
            headers={"Date": "Wed, 21 Oct 2015 07:28:00 GMT"},
        )

        server_time = self.async_run_with_timeout(get_current_server_time(throttler=create_throttler()))

        # 2015-10-21T07:28:00Z in epoch ms
        self.assertEqual(1445412480000.0, server_time)

    @aioresponses()
    def test_get_current_server_time_raises_when_date_header_missing(self, mock_api):
        url = public_rest_url(path_url=CONSTANTS.SYMBOLS_PATH_URL)
        mock_api.get(url, body="[]")

        with self.assertRaises(IOError):
            self.async_run_with_timeout(get_current_server_time())

    @aioresponses()
    def test_get_current_server_time_raises_on_http_error(self, mock_api):
        url = public_rest_url(path_url=CONSTANTS.SYMBOLS_PATH_URL)
        mock_api.get(url, status=500, body="oops")

        with self.assertRaises(IOError):
            self.async_run_with_timeout(get_current_server_time())
