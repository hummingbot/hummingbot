import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class FeesTest(unittest.TestCase):
    def test_get_transaction_summary(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/transaction_summary",
                json=expected_response,
            )
            summary = client.get_transaction_summary(
                "product_type", "contract_expiry_type", "product_venue"
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "product_type=product_type&contract_expiry_type=contract_expiry_type&product_venue=product_venue",
            )
            self.assertEqual(summary.__dict__, expected_response)
