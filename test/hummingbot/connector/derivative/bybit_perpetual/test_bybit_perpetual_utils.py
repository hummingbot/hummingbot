from unittest import TestCase

import pandas as pd

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS, bybit_perpetual_utils as utils


class BybitPerpetualUtilsTests(TestCase):
    def test_trading_pair_convertion(self):
        trading_pair = "BTC-USDT"
        self.assertEqual("BTCUSDT", utils.convert_to_exchange_trading_pair(trading_pair))

    def test_rest_api_path_for_endpoint(self):
        endpoint = {"linear": "/testEndpoint/linear",
                    "non_linear": "/testEndpoint/non_linear"}

        api_path = utils.rest_api_path_for_endpoint(endpoint=endpoint)
        self.assertEqual("/testEndpoint/linear", api_path)

        api_path = utils.rest_api_path_for_endpoint(endpoint=endpoint, trading_pair="BTC-USD")
        self.assertEqual("/testEndpoint/non_linear", api_path)

        api_path = utils.rest_api_path_for_endpoint(endpoint=endpoint, trading_pair="BTC-USDT")
        self.assertEqual("/testEndpoint/linear", api_path)

    def test_rest_api_url(self):
        endpoint = "/testEndpoint"

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain=None, )
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_main") + "/testEndpoint", url)

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain="bybit_perpetual_main")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_main") + "/testEndpoint", url)

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain="bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_testnet") + "/testEndpoint", url)

    def test_wss_linear_public_url(self):
        url = utils.wss_linear_public_url(None)
        self.assertEqual(CONSTANTS.WSS_LINEAR_PUBLIC_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_linear_public_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_LINEAR_PUBLIC_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_linear_public_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_LINEAR_PUBLIC_URLS.get("bybit_perpetual_testnet"), url)

    def test_wss_linear_private_url(self):
        url = utils.wss_linear_private_url(None)
        self.assertEqual(CONSTANTS.WSS_LINEAR_PRIVATE_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_linear_private_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_LINEAR_PRIVATE_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_linear_private_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_LINEAR_PRIVATE_URLS.get("bybit_perpetual_testnet"), url)

    def test_wss_non_linear_public_url(self):
        url = utils.wss_non_linear_public_url(None)
        self.assertEqual(CONSTANTS.WSS_NON_LINEAR_PUBLIC_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_non_linear_public_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_NON_LINEAR_PUBLIC_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_non_linear_public_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_NON_LINEAR_PUBLIC_URLS.get("bybit_perpetual_testnet"), url)

    def test_wss_non_linear_private_url(self):
        url = utils.wss_non_linear_private_url(None)
        self.assertEqual(CONSTANTS.WSS_NON_LINEAR_PRIVATE_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_non_linear_private_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_NON_LINEAR_PRIVATE_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_non_linear_private_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_NON_LINEAR_PRIVATE_URLS.get("bybit_perpetual_testnet"), url)

    def test_get_next_funding_timestamp(self):
        # Simulate 01:00 UTC
        timestamp = pd.Timestamp("2021-08-21-01:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-21-08:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # Simulate 09:00 UTC
        timestamp = pd.Timestamp("2021-08-21-09:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-21-16:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # Simulate 17:00 UTC
        timestamp = pd.Timestamp("2021-08-21-17:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-22-00:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))
