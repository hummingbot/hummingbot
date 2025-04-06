import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class ProductsTest(unittest.TestCase):
    def test_get_products(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/products",
                json=expected_response,
            )
            products = client.get_products(limit=2, product_type="SPOT")

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "limit=2&product_type=spot&get_tradability_status=false&get_all_products=false",
            )
            self.assertEqual(products.__dict__, expected_response)

    def test_get_product(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"product_id": "product_1"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/products/product_1",
                json=expected_response,
            )
            product = client.get_product("product_1")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "get_tradability_status=false")
            self.assertEqual(product.__dict__, expected_response)

    def test_get_product_book(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/product_book",
                json=expected_response,
            )
            book = client.get_product_book("product_1", 10)

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "product_id=product_1&limit=10")
            self.assertEqual(book.__dict__, expected_response)

    def test_get_best_bid_ask(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/best_bid_ask",
                json=expected_response,
            )
            bid_ask = client.get_best_bid_ask(["product_1", "product_2"])

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query, "product_ids=product_1&product_ids=product_2"
            )
            self.assertEqual(bid_ask.__dict__, expected_response)
