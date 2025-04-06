import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class PerpetualsTest(unittest.TestCase):
    def test_allocate_portfolio(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/intx/allocate",
                json=expected_response,
            )
            response = client.allocate_portfolio(
                portfolio_uuid="test_uuid",
                symbol="BTC-PERP-INTX",
                amount="100",
                currency="USD",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "portfolio_uuid": "test_uuid",
                    "symbol": "BTC-PERP-INTX",
                    "amount": "100",
                    "currency": "USD",
                },
            )
            self.assertEqual(response.__dict__, expected_response)

    def test_get_perps_portfolio_summary(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/intx/portfolio/test_uuid",
                json=expected_response,
            )
            portfolios = client.get_perps_portfolio_summary(portfolio_uuid="test_uuid")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(portfolios.__dict__, expected_response)

    def test_list_perps_positions(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/intx/positions/test_uuid",
                json=expected_response,
            )
            portfolios = client.list_perps_positions(portfolio_uuid="test_uuid")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(portfolios.__dict__, expected_response)

    def test_get_perps_position(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/intx/positions/test_uuid/BTC-PERP-INTX",
                json=expected_response,
            )
            portfolios = client.get_perps_position(
                portfolio_uuid="test_uuid", symbol="BTC-PERP-INTX"
            )

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(portfolios.__dict__, expected_response)

    def test_get_perps_portfolio_balances(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/intx/balances/test_uuid",
                json=expected_response,
            )
            portfolios = client.get_perps_portfolio_balances(portfolio_uuid="test_uuid")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(portfolios.__dict__, expected_response)

    def test_opt_in_or_out_multi_asset_collateral(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"key_1": "value_1", "key_2": "value_2"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/intx/multi_asset_collateral",
                json=expected_response,
            )
            response = client.opt_in_or_out_multi_asset_collateral(
                portfolio_uuid="test_uuid",
                multi_asset_collateral_enabled=True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "portfolio_uuid": "test_uuid",
                    "multi_asset_collateral_enabled": True,
                },
            )
            self.assertEqual(response.__dict__, expected_response)
