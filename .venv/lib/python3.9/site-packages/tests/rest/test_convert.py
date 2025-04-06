import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class ConvertTest(unittest.TestCase):
    def test_create_convert_quote(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"quote_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/convert/quote",
                json=expected_response,
            )
            quote = client.create_convert_quote(
                "from_account",
                "to_account",
                "100",
                user_incentive_id="1234",
                code_val="test_val",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "from_account": "from_account",
                    "to_account": "to_account",
                    "amount": "100",
                    "trade_incentive_metadata": {
                        "user_incentive_id": "1234",
                        "code_val": "test_val",
                    },
                },
            )
            self.assertEqual(quote.__dict__, expected_response)

    def test_get_convert_trade(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"trade_id": "1234"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/convert/trade/1234",
                json=expected_response,
            )
            trade = client.get_convert_trade("1234", "from_account", "to_account")

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "from_account=from_account&to_account=to_account",
            )
            self.assertEqual(trade.__dict__, expected_response)

    def test_commit_convert_trade(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"trade_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/convert/trade/1234",
                json=expected_response,
            )
            trade = client.commit_convert_trade("1234", "from_account", "to_account")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {"from_account": "from_account", "to_account": "to_account"},
            )
            self.assertEqual(trade.__dict__, expected_response)
