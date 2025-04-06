import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class PaymentsTest(unittest.TestCase):
    def test_list_payment_methods(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"accounts": [{"uuid": "payment1"}, {"name": "payment2"}]}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/payment_methods",
                json=expected_response,
            )
            payments = client.list_payment_methods()

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(payments.__dict__, expected_response)

    def test_get_payment_method(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"uuid": "payment1"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/payment_methods/payment1",
                json=expected_response,
            )
            payment = client.get_payment_method("payment1")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(payment.__dict__, expected_response)
