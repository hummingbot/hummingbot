import unittest

from hummingbot.connector.exchange.okex.okex_auth import OKExAuth
from unittest import mock


class TestAuth(unittest.TestCase):
    def setUp(self):

        # cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        okex_api_key = "OKEX_API_KEY_mock"
        okex_secret_key = "OKEX_SECRET_KEY_mock"
        okex_passphrase = "OKEX_PASSPHRASE_mock"

        self.auth = OKExAuth(okex_api_key, okex_secret_key, okex_passphrase)

    @mock.patch('time.time', mock.MagicMock(return_value=1595342544.567561))
    def test_aut_without_params(self):
        headers = self.auth.add_auth_to_params('get', "api/v5/account/balance", {})

        self.assertEqual(headers["OK-ACCESS-KEY"], "OKEX_API_KEY_mock")
        self.assertEqual(headers["OK-ACCESS-SIGN"], "j7mnZZsed1WZj472xg2DKPuGOP4KJKUfDem+KYQgYKw=")
        self.assertEqual(headers["OK-ACCESS-TIMESTAMP"], '2020-07-21T14:42:24.567Z')
        self.assertEqual(headers["OK-ACCESS-PASSPHRASE"], "OKEX_PASSPHRASE_mock")
