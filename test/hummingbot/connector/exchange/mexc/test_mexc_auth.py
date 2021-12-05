import unittest

from unittest import mock

from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth


class TestAuth(unittest.TestCase):
    def setUp(self):
        # cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        mexc_api_key = "MEXC_API_KEY_mock"
        mexc_secret_key = "MEXC_SECRET_KEY_mock"

        self.auth = MexcAuth(mexc_api_key, mexc_secret_key)

    @mock.patch('hummingbot.connector.exchange.mexc.mexc_utils.seconds', mock.MagicMock(return_value=1635249347))
    def test_auth_without_params(self):
        headers = self.auth.add_auth_to_params('GET', "/open/api/v2/market/coin/list",
                                               {'api_key': "MEXC_API_KEY_mock"}, True)
        self.assertIn("api_key=MEXC_API_KEY_mock&req_time=1635249347"
                      "&sign=8dc59c2b7f0ad6da9e8844bb5478595a4f83126cb607524d767586437bae8d68", headers)
