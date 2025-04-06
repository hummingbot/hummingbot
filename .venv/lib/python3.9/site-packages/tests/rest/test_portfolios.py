import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class PortfoliosTest(unittest.TestCase):
    def test_get_portfolios(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/portfolios",
                json=expected_response,
            )
            portfolios = client.get_portfolios("DEFAULT")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "portfolio_type=default")
            self.assertEqual(portfolios.__dict__, expected_response)

    def test_create_portfolio(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/portfolios",
                json=expected_response,
            )
            portfolio = client.create_portfolio("Test Portfolio")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(captured_json, {"name": "Test Portfolio"})
            self.assertEqual(portfolio.__dict__, expected_response)

    def test_get_portfolio_breakdown(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/portfolios/1234",
                json=expected_response,
            )
            breakdown = client.get_portfolio_breakdown("1234", "USD")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "currency=usd")
            self.assertEqual(breakdown.__dict__, expected_response)

    def test_move_portfolio_funds(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/portfolios/move_funds",
                json=expected_response,
            )
            move = client.move_portfolio_funds("100", "USD", "1234", "5678")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "funds": {"value": "100", "currency": "USD"},
                    "source_portfolio_uuid": "1234",
                    "target_portfolio_uuid": "5678",
                },
            )
            self.assertEqual(move.__dict__, expected_response)

    def test_edit_portfolio(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "PUT",
                "https://api.coinbase.com/api/v3/brokerage/portfolios/1234",
                json=expected_response,
            )
            edit = client.edit_portfolio("1234", "Test Portfolio")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(captured_json, {"name": "Test Portfolio"})
            self.assertEqual(edit.__dict__, expected_response)

    def test_delete_portfolio(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "DELETE",
                "https://api.coinbase.com/api/v3/brokerage/portfolios/1234",
                json=expected_response,
            )
            delete = client.delete_portfolio("1234")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(delete.__dict__, expected_response)
