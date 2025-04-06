import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class MarketDataTest(unittest.TestCase):
    def test_get_candles(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/products/product_id_1/candles",
                json=expected_response,
            )
            candles = client.get_candles(
                "product_id_1", "1640995200", "1641081600", "FIVE_MINUTE", 2
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "start=1640995200&end=1641081600&granularity=five_minute&limit=2",
            )
            self.assertEqual(candles.__dict__, expected_response)

    def test_get_market_trades(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/products/product_id/ticker",
                json=expected_response,
            )
            trades = client.get_market_trades(
                "product_id", 10, "1640995200", "1641081600"
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query, "limit=10&start=1640995200&end=1641081600"
            )
            self.assertEqual(trades.__dict__, expected_response)
