import unittest

from unittest import mock

from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth


class TestAuth(unittest.TestCase):

    @property
    def api_key(self):
        return 'MEXC_API_KEY_mock'

    @property
    def secret_key(self):
        return 'MEXC_SECRET_KEY_mock'

    @mock.patch('hummingbot.connector.exchange.mexc.mexc_utils.seconds', mock.MagicMock(return_value=1635249347))
    def test_auth_without_params(self):
        self.auth = MexcAuth(self.api_key, self.secret_key)
        headers = self.auth.add_auth_to_params('GET', "/open/api/v2/market/coin/list",
                                               {'api_key': self.api_key}, True)
        self.assertIn("api_key=MEXC_API_KEY_mock&req_time=1635249347"
                      "&sign=8dc59c2b7f0ad6da9e8844bb5478595a4f83126cb607524d767586437bae8d68", headers)
