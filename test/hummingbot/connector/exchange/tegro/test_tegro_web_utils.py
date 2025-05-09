import asyncio
import unittest
from typing import Awaitable

import hummingbot.connector.exchange.tegro.tegro_constants as CONSTANTS
import hummingbot.connector.exchange.tegro.tegro_web_utils as web_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class TegroUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_url_main_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.TEGRO_BASE_URL}{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_rest_url_testnet_domain(self):
        path_url = "/TEST_PATH_URL"

        expected_url = f"{CONSTANTS.TESTNET_BASE_URL}{path_url}"
        self.assertEqual(
            expected_url, web_utils.public_rest_url(path_url=path_url, domain="testnet")
        )

    def test_wss_url_main_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.TEGRO_WS_URL}{endpoint}"
        self.assertEqual(expected_url, web_utils.wss_url(endpoint=endpoint))

    def test_wss_url_testnet_domain(self):
        endpoint = "TEST_SUBSCRIBE"

        expected_url = f"{CONSTANTS.TESTNET_WS_URL}{endpoint}"
        self.assertEqual(expected_url, web_utils.wss_url(endpoint=endpoint, domain="testnet"))

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory(
            time_synchronizer=TimeSynchronizer(),
            time_provider=lambda: None,
        )

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))
