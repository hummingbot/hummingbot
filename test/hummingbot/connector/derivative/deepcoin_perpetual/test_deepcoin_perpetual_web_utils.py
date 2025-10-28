import asyncio
import json
import unittest
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.derivative.deepcoin_perpetual import (
    deepcoin_perpetual_constants as CONSTANTS,
    deepcoin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DeepcoinPerpetualWebUtilsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.pre_processor = web_utils.HeadersContentRESTPreProcessor()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))

    def test_build_api_factory_without_time_synchronizer_pre_processor(self):
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(
            throttler=web_utils.create_throttler()
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(1, len(api_factory._rest_pre_processors))

    @aioresponses()
    def test_get_current_server_time(self, mock_api):
        response = {"code": "0", "msg": "", "data": [{"ts": "1597026383085"}]}

        mock_api.get(web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL), body=json.dumps(response))

        response = self.async_run_with_timeout(web_utils.get_current_server_time())
        self.assertEqual(response, 1597026383085)

    def test_public_rest_url(self):
        self.assertEqual(
            web_utils.public_rest_url(CONSTANTS.FUNDING_INFO_URL, CONSTANTS.DEFAULT_DOMAIN),
            "https://api.deepcoin.com/deepcoin/trade/funding-rate",
        )

    def test_public_wss_url(self):
        self.assertEqual(
            web_utils.public_wss_url(CONSTANTS.DEFAULT_DOMAIN),
            "wss://stream.deepcoin.com/streamlet/trade/public/swap?platform=api",
        )
