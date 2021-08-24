import pandas as pd

from unittest import TestCase

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS, bybit_perpetual_utils as utils


class BybitPerpetualUtilsTests(TestCase):

    def test_trading_pair_convertion(self):
        trading_pair = "BTC-USDT"
        self.assertEqual("BTCUSDT", utils.convert_to_exchange_trading_pair(trading_pair))

    def test_rest_api_url(self):
        url = utils.rest_api_url_for_endpoint(endpoint="/testEndpoint", domain=None)
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_main") + CONSTANTS.REST_API_VERSION + "/testEndpoint", url)

        url = utils.rest_api_url_for_endpoint(endpoint="/testEndpoint", domain="bybit_main")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_main") + CONSTANTS.REST_API_VERSION + "/testEndpoint", url)

        url = utils.rest_api_url_for_endpoint(endpoint="/testEndpoint", domain="bybit_testnet")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_testnet") + CONSTANTS.REST_API_VERSION + "/testEndpoint", url)

    def test_wss_url(self):
        url = utils.wss_url(None)
        self.assertEqual(CONSTANTS.WSS_URLS.get("bybit_main"), url)

        url = utils.wss_url("bybit_main")
        self.assertEqual(CONSTANTS.WSS_URLS.get("bybit_main"), url)

        url = utils.wss_url("bybit_testnet")
        self.assertEqual(CONSTANTS.WSS_URLS.get("bybit_testnet"), url)

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
