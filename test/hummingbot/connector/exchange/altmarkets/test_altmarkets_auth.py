from unittest.mock import patch

from unittest import TestCase

from hummingbot.connector.exchange.altmarkets.altmarkets_auth import AltmarketsAuth
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants


class AltmarketsAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._api_key = 'testApiKey'
        self._secret_key = 'testSecretKey'
        self._username = 'testUserName'

        self.auth = AltmarketsAuth(
            api_key=self._api_key,
            secret_key=self._secret_key
        )

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_auth.AltmarketsAuth._nonce")
    def test_get_headers(self, nonce_mock):
        nonce_mock.return_value = '1234567899'
        headers = self.auth.get_headers()

        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual(self._api_key, headers["X-Auth-Apikey"])
        self.assertEqual('1234567899', headers["X-Auth-Nonce"])
        self.assertEqual('13e611ce9c44f18aced4905a9cfb9133fddb1f85d02e1d3764a6aaf1803a22b0',        # noqa: mock
                         headers["X-Auth-Signature"])
        self.assertEqual(Constants.USER_AGENT, headers["User-Agent"])
