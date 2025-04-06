import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient

from ..constants import TEST_API_KEY, TEST_API_SECRET


class DataApiTest(unittest.TestCase):
    def test_get_api_key_permissions(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {
            "can_view": True,
            "can_trade": False,
            "can_withdraw": False,
            "portfolio_uuid": "portfolio1",
        }

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/key_permissions",
                json=expected_response,
            )
            key_permissions = client.get_api_key_permissions()

            self.assertEqual(key_permissions.__dict__, expected_response)
