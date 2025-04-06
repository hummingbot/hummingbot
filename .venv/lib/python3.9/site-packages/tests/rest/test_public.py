import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class PublicTest(unittest.TestCase):
    def test_authenticated_request(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"iso": "2022-01-01T00:00:00Z", "epoch": 1640995200}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/time",
                json=expected_response,
            )
            time = client.get_unix_time()

            captured_request = m.request_history[0]
            captured_headers = captured_request.headers

            self.assertEqual(captured_request.query, "")
            self.assertEqual(time.__dict__, expected_response)
            self.assertIn("Authorization", captured_headers)

    def test_unauthenticated_request(self):
        client = RESTClient()

        expected_response = {"iso": "2022-01-01T00:00:00Z", "epoch": 1640995200}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/time",
                json=expected_response,
            )
            time = client.get_unix_time()

            captured_request = m.request_history[0]
            captured_headers = captured_request.headers

            self.assertEqual(captured_request.query, "")
            self.assertEqual(time.__dict__, expected_response)
            self.assertNotIn("Authorization", captured_headers)

    def test_get_time(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"iso": "2022-01-01T00:00:00Z", "epoch": 1640995200}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/time",
                json=expected_response,
            )
            time = client.get_unix_time()

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(time.__dict__, expected_response)

    def test_get_public_product_book(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/market/product_book",
                json=expected_response,
            )
            book = client.get_public_product_book("product_1", 10)

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "product_id=product_1&limit=10")
            self.assertEqual(book.__dict__, expected_response)

    def test_get_public_products(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/market/products",
                json=expected_response,
            )
            products = client.get_public_products(limit=2, product_type="SPOT")

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "limit=2&product_type=spot&get_all_products=false",
            )
            self.assertEqual(products.__dict__, expected_response)

    def test_get_public_product(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"product_id": "product_1"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/market/products/product_1",
                json=expected_response,
            )
            product = client.get_public_product("product_1")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(product.__dict__, expected_response)

    def test_get_public_candles(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/market/products/product_id_1/candles",
                json=expected_response,
            )
            candles = client.get_public_candles(
                "product_id_1", "1640995200", "1641081600", "FIVE_MINUTE", 2
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "start=1640995200&end=1641081600&granularity=five_minute&limit=2",
            )
            self.assertEqual(candles.__dict__, expected_response)

    def test_get_public_market_trades(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/market/products/product_id/ticker",
                json=expected_response,
            )
            trades = client.get_public_market_trades(
                "product_id", 10, "1640995200", "1641081600"
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query, "limit=10&start=1640995200&end=1641081600"
            )
            self.assertEqual(trades.__dict__, expected_response)
