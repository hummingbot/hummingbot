
import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from web3 import Web3

from hummingbot.connector.derivative.derive_perpetual import derive_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth import DerivePerpetualAuth
from hummingbot.connector.other.derive_common_utils import RESTING_ORDER_VALIDITY_SEC, SESSION_KEY_EXPIRY_MARGIN_SEC
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DerivePerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
        self.session_private_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.subacct_id = "45686"  # noqa: mock
        self.domain = "derive_perpetual_testnet"  # noqa: mock
        self.auth = DerivePerpetualAuth(wallet_address=self.wallet_address,
                                        session_private_key=self.session_private_key,
                                        subacct_id=self.subacct_id,
                                        trading_required=True,
                                        domain=self.domain)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_initialization(self):
        self.assertEqual(self.auth._wallet_address, self.wallet_address)
        self.assertEqual(self.auth._session_private_key, self.session_private_key)
        self.assertEqual(self.auth._subacct_id, int(self.subacct_id))
        self.assertTrue(self.auth._trading_required)
        self.assertIsInstance(self.auth._w3, Web3)

    def _auth_for(self, subacct_id, trading_required: bool = True) -> DerivePerpetualAuth:
        return DerivePerpetualAuth(
            wallet_address=self.wallet_address,
            session_private_key=self.session_private_key,
            subacct_id=subacct_id,
            trading_required=trading_required,
            domain=self.domain,
        )

    def test_subaccount_id_is_an_integer_however_it_was_configured(self):
        """
        Credentials reach the connector as strings, while v3 declares the subaccount id an integer
        and most routes hold to it: public/get_trade_history answers {"subaccount_id": "45686"}
        with -32602 "invalid type: string, expected i64". The id is normalised once so that no
        request body can carry the string.
        """
        self.assertEqual(45686, self.auth._subacct_id)
        self.assertIsInstance(self.auth._subacct_id, int)

        for configured in (45686, " 45686 "):
            self.assertEqual(45686, self._auth_for(configured)._subacct_id)

    def test_missing_subaccount_id_is_tolerated_and_a_malformed_one_is_named(self):
        # The trading-pair fetcher builds a connector with empty placeholder credentials.
        for placeholder in (None, ""):
            self.assertIsNone(self._auth_for(placeholder, trading_required=False)._subacct_id)

        with self.assertRaises(ValueError) as context:
            self._auth_for("main-account")
        self.assertIn("must be a whole number", str(context.exception))

    def _signed_order(self, **order):
        params = {
            "asset_address": "0x1234567890abcdef1234567890abcdef12345678",  # noqa: mock
            "sub_id": 0,
            "limit_price": "100",
            "amount": "10",
            "max_fee": "1",
            "recipient_id": 45686,
            "is_bid": True,
        }
        params.update(order)
        return self.auth.sign(params)

    def test_resting_order_is_signed_for_as_long_as_the_api_allows(self):
        """
        v3 expires an order when its signature does, whatever its time in force. Signing a GTC
        order for an hour pulled it from the book an hour later, where v2's far-future expiry
        left it until it was filled or cancelled.
        """
        now = 1_700_000_000
        with patch("hummingbot.connector.other.derive_common_utils.time.time", return_value=now):
            for time_in_force in ("gtc", "post_only"):
                signed = self._signed_order(order_type="limit", time_in_force=time_in_force)
                self.assertEqual(now + RESTING_ORDER_VALIDITY_SEC, signed["signature_expiry_sec"], time_in_force)

        # 119 days: the API's 120 day ceiling, less a day of headroom for clock drift.
        self.assertEqual(119 * 24 * 60 * 60, RESTING_ORDER_VALIDITY_SEC)

    def test_order_that_cannot_rest_is_signed_for_a_short_window(self):
        now = 1_700_000_000
        with patch("hummingbot.connector.other.derive_common_utils.time.time", return_value=now):
            for order_type, time_in_force in (("market", "ioc"), ("limit", "ioc"), ("limit", "fok")):
                signed = self._signed_order(order_type=order_type, time_in_force=time_in_force)
                self.assertEqual(
                    now + CONSTANTS.SIGNATURE_VALIDITY_SEC,
                    signed["signature_expiry_sec"],
                    f"{order_type}/{time_in_force}",
                )

    def test_signature_never_outlives_the_session_key(self):
        """An action that outlives the key that signed it is refused with 14038."""
        now = 1_700_000_000
        self.auth.session_key_expiry_sec = now + 7 * 24 * 60 * 60
        with patch("hummingbot.connector.other.derive_common_utils.time.time", return_value=now):
            resting = self._signed_order(order_type="limit", time_in_force="gtc")
            immediate = self._signed_order(order_type="market", time_in_force="ioc")

        self.assertEqual(
            self.auth.session_key_expiry_sec - SESSION_KEY_EXPIRY_MARGIN_SEC, resting["signature_expiry_sec"]
        )
        # Already inside the key's lifetime, so left alone.
        self.assertEqual(now + CONSTANTS.SIGNATURE_VALIDITY_SEC, immediate["signature_expiry_sec"])

    def test_order_is_refused_once_the_session_key_is_about_to_expire(self):
        now = 1_700_000_000
        with patch("hummingbot.connector.other.derive_common_utils.time.time", return_value=now):
            self.auth.session_key_expiry_sec = now + 120
            with self.assertRaises(ValueError) as context:
                self._signed_order(order_type="limit", time_in_force="gtc")
            self.assertIn("expires in 120 seconds", str(context.exception))

            self.auth.session_key_expiry_sec = now - 5
            with self.assertRaises(ValueError) as context:
                self._signed_order(order_type="market", time_in_force="ioc")
            self.assertIn("has expired", str(context.exception))

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth.DerivePerpetualAuth.utc_now_ms")
    def test_header_for_authentication(self, mock_utc_now):
        mock_utc_now.return_value = 1234567890
        mock_signature = "0x123signature"

        mock_account = MagicMock()
        mock_account.sign_message.return_value.signature.to_0x_hex.return_value = mock_signature
        self.auth._w3.eth.account = mock_account

        headers = self.auth.header_for_authentication()

        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["X-DeriveWallet"], self.wallet_address)
        self.assertEqual(headers["X-DeriveTimestamp"], "1234567890")
        self.assertEqual(headers["X-DeriveSignature"], mock_signature)

    @patch("hummingbot.core.web_assistant.connections.data_types.WSRequest.send_with_connection")
    def test_ws_authenticate(self, mock_send):
        mock_send.return_value = None
        request = MagicMock(spec=WSRequest)
        request.endpoint = None
        request.payload = {}

        authenticated_request = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(authenticated_request.endpoint, request.endpoint)
        self.assertEqual(authenticated_request.payload, request.payload)

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth.DerivePerpetualAuth.header_for_authentication")
    def test_rest_authenticate(self, mock_header_for_auth):
        mock_header_for_auth.return_value = {"header": "value"}

        request = RESTRequest(
            method=RESTMethod.POST, url="/test", data=json.dumps({"key": "value"}), headers={}
        )

        authenticated_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("header", authenticated_request.headers)
        self.assertEqual(authenticated_request.headers["header"], "value")
        self.assertEqual(authenticated_request.data, json.dumps({"key": "value"}))

    def test_add_auth_to_params_post(self):
        import eth_utils
        address = "0x1234567890abcdef1234567890abcdef12345678"
        self.assertTrue(eth_utils.is_hex_address(address))
        params = {
            "type": "order",
            # This needs to be 0x40-long
            "asset_address": address,
            "sub_id": 1,
            "limit_price": "100",
            "amount": "10",
            "max_fee": "1",
            "recipient_id": 2,
            "is_bid": True
        }
        request = MagicMock(method=RESTMethod.POST)

        with patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth.SignedAction.sign") as mock_sign, \
                patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_web_utils.order_to_call") as mock_order_to_call:
            mock_order_to_call.return_value = params
            mock_sign.return_value = None

            updated_params = self.auth.add_auth_to_params_post(params, request)
            self.assertIsInstance(updated_params, str)

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth.DerivePerpetualAuth.utc_now_ms")
    def test_get_ws_auth_payload(self, mock_utc_now):
        mock_utc_now.return_value = 1234567890
        mock_signature = "0x123signature"

        mock_account = MagicMock()
        mock_account.sign_message.return_value.signature.to_0x_hex.return_value = mock_signature
        self.auth._w3.eth.account = mock_account

        payload = self.auth.get_ws_auth_payload()

        self.assertEqual(payload["wallet"], self.wallet_address)
        self.assertEqual(payload["timestamp"], 1234567890)
        self.assertIsInstance(payload["timestamp"], int)
        self.assertEqual(payload["signature"], mock_signature)

    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_auth.DerivePerpetualAuth.utc_now_ms")
    def test_utc_now_ms(self, mock_utc_now):
        mock_utc_now.return_value = 1234567890
        timestamp = self.auth.utc_now_ms()
        self.assertEqual(timestamp, 1234567890)
