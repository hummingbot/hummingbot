import unittest
from unittest.mock import Mock, patch

import hummingbot.connector.exchange.dexalot.dexalot_constants as CONSTANTS
from hummingbot.connector.exchange.dexalot import dexalot_web_utils as web_utils
from hummingbot.connector.exchange.dexalot.dexalot_web_utils import create_throttler
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DexalotUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    @patch.object(WebAssistantsFactory, "__init__", return_value=None)
    def test_build_api_factory_without_time_synchronizer_pre_processor(self, mock_factory):
        throttler = Mock()
        web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler)
        mock_factory.assert_called_once_with(throttler=throttler)

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))

    def test_create_throttler(self):
        throttler = create_throttler()
        self.assertIsInstance(throttler, AsyncThrottler)
