import asyncio
import json
import unittest
from typing import Awaitable
from unittest.mock import Mock, patch

from aioresponses import aioresponses

from hummingbot.connector.derivative.dydx_v4_perpetual import (
    dydx_v4_perpetual_constants as CONSTANTS,
    dydx_v4_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DydxV4PerpetualWebUtilsTest(unittest.TestCase):

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_public_rest_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PATH_MARKETS)
        self.assertEqual("https://indexer.dydx.trade/v4/perpetualMarkets", url)

    @patch("hummingbot.connector.derivative.dydx_v4_perpetual.dydx_v4_perpetual_web_utils"
           ".create_throttler", return_value=Mock())
    def test_build_api_factory(self, mock_create_throttler):
        throttler = web_utils.create_throttler()
        api_factory = web_utils.build_api_factory(throttler)
        mock_create_throttler.assert_called_once()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    def test_build_api_factory_without_time_synchronizer_pre_processor(self, mock_factory):
        throttler = Mock()
        web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler)
        mock_factory.assert_called_once_with(throttler=throttler)

    @aioresponses()
    def test_get_current_server_time(self, api_mock):
        throttler = web_utils.create_throttler()
        url = web_utils.public_rest_url(path_url=CONSTANTS.PATH_TIME)
        data = {'iso': '2024-05-15T10:38:19.795Z', 'epoch': 1715769499.795}

        api_mock.get(url=url, body=json.dumps(data))

        time = self.async_run_with_timeout(web_utils.get_current_server_time(throttler))

        self.assertEqual(data["epoch"], time)
