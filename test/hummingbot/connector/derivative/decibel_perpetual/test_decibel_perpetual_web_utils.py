from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils import (
    build_api_factory,
    fullnode_url,
    get_current_server_time,
    get_package_address,
    private_rest_url,
    public_rest_url,
    wss_url,
)


class TestDecibelPerpetualWebUtils(IsolatedAsyncioWrapperTestCase):
    level = 0

    def test_public_rest_url_mainnet(self):
        url = public_rest_url("/api/v1/markets", CONSTANTS.DEFAULT_DOMAIN)
        self.assertIn("mainnet", url)
        self.assertIn("/api/v1/markets", url)

    def test_public_rest_url_testnet(self):
        url = public_rest_url("/api/v1/markets", CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)
        self.assertIn("/api/v1/markets", url)

    def test_public_rest_url_netna(self):
        url = public_rest_url("/api/v1/markets", CONSTANTS.NETNA_DOMAIN)
        self.assertIn("netna", url)
        self.assertIn("/api/v1/markets", url)

    def test_private_rest_url_mainnet(self):
        url = private_rest_url("/api/v1/account_overviews", CONSTANTS.DEFAULT_DOMAIN)
        self.assertIn("mainnet", url)

    def test_private_rest_url_testnet(self):
        url = private_rest_url("/api/v1/account_overviews", CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)

    def test_private_rest_url_netna(self):
        url = private_rest_url("/api/v1/account_overviews", CONSTANTS.NETNA_DOMAIN)
        self.assertIn("netna", url)

    def test_wss_url_mainnet(self):
        url = wss_url(CONSTANTS.DEFAULT_DOMAIN)
        self.assertIn("mainnet", url)
        self.assertTrue(url.startswith("wss://"))

    def test_wss_url_testnet(self):
        url = wss_url(CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)
        self.assertTrue(url.startswith("wss://"))

    def test_wss_url_netna(self):
        url = wss_url(CONSTANTS.NETNA_DOMAIN)
        self.assertIn("netna", url)
        self.assertTrue(url.startswith("wss://"))

    def test_fullnode_url_mainnet(self):
        url = fullnode_url(CONSTANTS.DEFAULT_DOMAIN)
        self.assertIn("mainnet", url)

    def test_fullnode_url_testnet(self):
        url = fullnode_url(CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)

    def test_fullnode_url_netna(self):
        url = fullnode_url(CONSTANTS.NETNA_DOMAIN)
        self.assertIn("netna", url)

    def test_get_package_address_mainnet(self):
        addr = get_package_address(CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual(CONSTANTS.MAINNET_PACKAGE, addr)

    def test_get_package_address_testnet(self):
        addr = get_package_address(CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(CONSTANTS.TESTNET_PACKAGE, addr)

    def test_get_package_address_netna(self):
        addr = get_package_address(CONSTANTS.NETNA_DOMAIN)
        self.assertEqual(CONSTANTS.NETNA_PACKAGE, addr)

    def test_build_api_factory(self):
        factory = build_api_factory(domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertIsNotNone(factory)

    async def test_get_current_server_time(self):
        result = await get_current_server_time()
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)
