import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import HyperliquidPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HyperliquidPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        # Address derived from api_secret below; required since the auth class now
        # validates that the supplied address matches the address derived from the
        # private key when use_vault is False (see issue #7866).
        self.api_address = "0x836eE2b55d173245832995082a8600709c38D099"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.connection_mode = "arb_wallet"
        self.use_vault = False
        self.trading_required = True  # noqa: mock
        self.auth = HyperliquidPerpetualAuth(
            api_address=self.api_address,
            api_secret=self.api_secret,
            use_vault=self.use_vault
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return 1678974447.926

    @patch(
        "hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth.HyperliquidPerpetualAuth._get_timestamp")
    def test_sign_order_params_post_request(self, ts_mock: MagicMock):
        params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": 4,
                "isBuy": True,
                "limitPx": 1201,
                "sz": 0.01,
                "reduceOnly": False,
                "orderType": {"limit": {"tif": "Gtc"}},
                "cloid": "0x000000000000000000000000000ee056",
            }
        }
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(params),
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        # raw_signature = f'/linear/v1/orders&one=1&timestamp={int(self._get_timestamp() * 1e3)}'
        # expected_signature = hmac.new(bytes(self.secret_key.encode("utf-8")),
        #                               raw_signature.encode("utf-8"),
        #                               hashlib.sha256).hexdigest()

        params = json.loads(request.data)
        self.assertEqual(4, len(params))
        self.assertEqual(None, params.get("vaultAddress"))
        self.assertEqual("order", params.get("action")["type"])


class HyperliquidPerpetualAuthValidationTests(TestCase):
    """Construction-time validation of api_address and api_secret (issue #7866)."""

    VALID_KEY = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
    DERIVED_ADDRESS = "0x836eE2b55d173245832995082a8600709c38D099"
    UNRELATED_ADDRESS = "0x000000000000000000000000000000000000dEaD"

    def test_invalid_private_key_format_raises(self):
        with self.assertRaises(ValueError) as ctx:
            HyperliquidPerpetualAuth(
                api_address=self.DERIVED_ADDRESS,
                api_secret="not-a-valid-hex-key",
                use_vault=False,
            )
        self.assertIn("private key", str(ctx.exception).lower())

    def test_invalid_address_format_raises(self):
        with self.assertRaises(ValueError) as ctx:
            HyperliquidPerpetualAuth(
                api_address="not_an_address",
                api_secret=self.VALID_KEY,
                use_vault=False,
            )
        self.assertIn("address", str(ctx.exception).lower())

    def test_address_does_not_match_key_raises(self):
        with self.assertRaises(ValueError) as ctx:
            HyperliquidPerpetualAuth(
                api_address=self.UNRELATED_ADDRESS,
                api_secret=self.VALID_KEY,
                use_vault=False,
            )
        message = str(ctx.exception).lower()
        self.assertIn("does not derive", message)
        self.assertIn(self.DERIVED_ADDRESS.lower(), message)

    def test_vault_mode_bypasses_address_match_check(self):
        # In vault mode, the supplied address is the vault, not the wallet derived
        # from the private key, so the derive-and-compare check must be skipped.
        auth = HyperliquidPerpetualAuth(
            api_address=self.UNRELATED_ADDRESS,
            api_secret=self.VALID_KEY,
            use_vault=True,
        )
        self.assertEqual(self.UNRELATED_ADDRESS, auth._vault_address)

    def test_api_wallet_mode_bypasses_address_match_check(self):
        # In api_wallet mode the private key is a Hyperliquid API/agent wallet
        # key, which by design does not derive to the user's trading address.
        # The derive-and-compare check must be skipped so the documented
        # api_wallet flow is not rejected (see #7866).
        auth = HyperliquidPerpetualAuth(
            api_address=self.UNRELATED_ADDRESS,
            api_secret=self.VALID_KEY,
            use_vault=False,
            connection_mode="api_wallet",
        )
        self.assertEqual(self.UNRELATED_ADDRESS, auth._api_address)
        self.assertIsNone(auth._vault_address)
        # The agent key is still parsed into a usable signing wallet even though
        # it does not match the supplied trading address.
        self.assertEqual(self.DERIVED_ADDRESS.lower(), auth.wallet.address.lower())

    def test_empty_inputs_raise(self):
        with self.assertRaises(ValueError):
            HyperliquidPerpetualAuth(api_address="", api_secret=self.VALID_KEY, use_vault=False)
        with self.assertRaises(ValueError):
            HyperliquidPerpetualAuth(api_address=self.DERIVED_ADDRESS, api_secret="", use_vault=False)
