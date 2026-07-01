from unittest import TestCase
from urllib.parse import urlparse

import hummingbot.connector.exchange.vertex.vertex_constants as CONSTANTS


class VertexConstantsTests(TestCase):
    """Regression coverage for the Vertex testnet endpoint URLs (PR #8227).

    The testnet WS subscribe URL previously had a doubled host typo
    (``gateway.vertexprotocol-vertexprotocol.com``) which silently broke
    every testnet websocket subscription. These tests pin the corrected
    value and guard the whole testnet URL family against the typo class.
    """

    def test_testnet_ws_subscribe_url_is_correct(self):
        self.assertEqual(
            "wss://gateway.sepolia-test.vertexprotocol.com/v1/subscribe",
            CONSTANTS.WS_SUBSCRIBE_URLS[CONSTANTS.TESTNET_DOMAIN],
        )

    def test_all_testnet_urls_share_the_sepolia_test_host(self):
        # Every testnet endpoint must resolve to the same sepolia-test host;
        # the #8227 bug was a single map entry diverging from this host.
        expected_host = "gateway.sepolia-test.vertexprotocol.com"
        for url_map in (
            CONSTANTS.BASE_URLS,
            CONSTANTS.WSS_URLS,
            CONSTANTS.WS_SUBSCRIBE_URLS,
        ):
            host = urlparse(url_map[CONSTANTS.TESTNET_DOMAIN]).hostname
            self.assertEqual(expected_host, host)

    def test_no_url_contains_the_doubled_host_typo(self):
        typo = "vertexprotocol-vertexprotocol"
        for url_map in (
            CONSTANTS.BASE_URLS,
            CONSTANTS.WSS_URLS,
            CONSTANTS.ARCHIVE_INDEXER_URLS,
            CONSTANTS.WS_SUBSCRIBE_URLS,
        ):
            for url in url_map.values():
                self.assertNotIn(typo, url)
