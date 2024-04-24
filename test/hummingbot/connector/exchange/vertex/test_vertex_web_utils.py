import asyncio
import time
from unittest import TestCase

from hummingbot.connector.exchange.vertex import vertex_constants as CONSTANTS, vertex_web_utils as web_utils


class WebUtilsTests(TestCase):
    def test_public_rest_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.QUERY_PATH_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual("https://gateway.prod.vertexprotocol.com/v1/query", url)
        url = web_utils.public_rest_url(path_url=CONSTANTS.QUERY_PATH_URL, domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual("https://gateway.sepolia-test.vertexprotocol.com/v1/query", url)

    def test_private_rest_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.QUERY_PATH_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual("https://gateway.prod.vertexprotocol.com/v1/query", url)
        url = web_utils.private_rest_url(path_url=CONSTANTS.QUERY_PATH_URL, domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual("https://gateway.sepolia-test.vertexprotocol.com/v1/query", url)

    def test_build_api_factory(self):
        self.assertIsNotNone(web_utils.build_api_factory())

    def test_create_throttler(self):
        self.assertIsNotNone(web_utils.create_throttler())

    def test_get_current_server_time(self):
        loop = asyncio.get_event_loop()
        recent_timestamp = time.time() - 1.0
        server_timestamp = loop.run_until_complete(
            asyncio.wait_for(web_utils.get_current_server_time(web_utils.create_throttler()), 1)
        )
        self.assertLess(recent_timestamp, server_timestamp)
