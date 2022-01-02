import hashlib
import hmac
from copy import copy
from unittest import TestCase

from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth


class BinanceAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "testSecret"

    def test_add_auth_params(self):
        now = 1234567890.000

        params = {
            "symbol": "LTCBTC",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": "0.1",
        }
        full_params = copy(params)

        auth = BinanceAuth(api_key=self._api_key, secret_key=self._secret)

        request_params = auth.add_auth_to_params(params, current_time=now)
        full_params.update({"timestamp": 1234567890000})
        encoded_params = "&".join([f"{key}={value}" for key, value in full_params.items()])
        expected_signature = hmac.new(
            self._secret.encode("utf-8"),
            encoded_params.encode("utf-8"),
            hashlib.sha256).hexdigest()
        self.assertEqual(now * 1e3, request_params["timestamp"])
        self.assertEqual(expected_signature, request_params["signature"])
