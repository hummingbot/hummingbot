import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import ANY, AsyncMock, Mock, patch

from hummingbot.connector.derivative.dydx_v4_perpetual import (
    dydx_v4_perpetual_constants as CONSTANTS,
    dydx_v4_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DydxV4PerpetualWebUtilsTest(unittest.TestCase):

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
