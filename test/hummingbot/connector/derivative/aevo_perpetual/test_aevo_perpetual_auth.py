import asyncio
import hashlib
import hmac
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class AevoPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test-key"
        self.api_secret = "test-secret"
        self.signing_key = "0x0000000000000000000000000000000000000000000000000000000000000001"  # noqa: mock
        self.account_address = "0x0000000000000000000000000000000000000002"  # noqa: mock
        self.auth = AevoPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            signing_key=self.signing_key,
            account_address=self.account_address,
            domain="aevo_perpetual",
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    @patch("hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth.time.time")
    def test_rest_authenticate_get(self, time_mock):
        time_mock.return_value = 1700000000.0
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.aevo.xyz/orderbook",
            params={"instrument_name": "ETH-PERP"},
            is_auth_required=True,
            headers={},
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        timestamp = str(int(1700000000.0 * 1e9))
        message = f"{self.api_key},{timestamp},GET,/orderbook,"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        self.assertEqual(timestamp, request.headers["AEVO-TIMESTAMP"])
        self.assertEqual(self.api_key, request.headers["AEVO-KEY"])
        self.assertEqual(signature, request.headers["AEVO-SIGNATURE"])

    def test_sign_order_returns_hex(self):
        signature = self.auth.sign_order(
            is_buy=True,
            limit_price=1000000,
            amount=2000000,
            salt=12345,
            instrument=1,
            timestamp=1690434000,
        )
        self.assertTrue(signature.startswith("0x"))
        self.assertEqual(132, len(signature))
