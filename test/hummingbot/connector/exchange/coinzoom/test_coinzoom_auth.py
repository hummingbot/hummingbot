from unittest import TestCase

from hummingbot.connector.exchange.coinzoom.coinzoom_auth import CoinzoomAuth


class CoinzoomAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._api_key = 'testApiKey'
        self._secret_key = 'testSecretKey'
        self._username = 'testUserName'

        self.auth = CoinzoomAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            username=self._username
        )

    def test_get_ws_params(self):
        params = self.auth.get_ws_params()

        self.assertEqual(self._api_key, params["apiKey"])
        self.assertEqual(self._secret_key, params["secretKey"])

    def test_get_headers(self):
        headers = self.auth.get_headers()

        self.assertEqual("application/json", headers["Content-Type"])
        self.assertEqual(self._api_key, headers["Coinzoom-Api-Key"])
        self.assertEqual(self._secret_key, headers["Coinzoom-Api-Secret"])
        self.assertEqual(f"hummingbot ZoomMe: {self._username}", headers["User-Agent"])
