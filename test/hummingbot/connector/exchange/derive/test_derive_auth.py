import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

import eth_utils
from web3 import Web3

from hummingbot.connector.exchange.derive.derive_auth import DeriveAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DeriveAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "0x1234567890abcdef1234567890abcdef12345678"  # noqa: mock
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.sub_id = "45686"  # noqa: mock
        self.domain = "derive_testnet"  # noqa: mock
        self.auth = DeriveAuth(api_key=self.api_key,
                               api_secret=self.api_secret,
                               sub_id=self.sub_id,
                               trading_required=True,
                               domain=self.domain)

    def test_initialization(self):
        self.assertEqual(self.auth._api_key, self.api_key)
        self.assertEqual(self.auth._api_secret, self.api_secret)
        self.assertEqual(self.auth._sub_id, self.sub_id)
        self.assertTrue(self.auth._trading_required)
        self.assertIsInstance(self.auth._w3, Web3)

    @patch("hummingbot.connector.exchange.derive.derive_auth.DeriveAuth.utc_now_ms")
    def test_header_for_authentication(self, mock_utc_now):
        mock_utc_now.return_value = 1234567890
        mock_signature = "0x123signature"

        mock_account = MagicMock()
        mock_account.sign_message.return_value.signature.to_0x_hex.return_value = mock_signature
        self.auth._w3.eth.account = mock_account

        headers = self.auth.header_for_authentication()

        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["X-LyraWallet"], self.api_key)
        self.assertEqual(headers["X-LyraTimestamp"], "1234567890")
        self.assertEqual(headers["X-LyraSignature"], mock_signature)

    @patch("hummingbot.core.web_assistant.connections.data_types.WSRequest.send_with_connection")
    async def test_ws_authenticate(self, mock_send):
        mock_send.return_value = None
        request = MagicMock(spec=WSRequest)
        request.endpoint = None
        request.payload = {}
        authenticated_request = await (self.auth.ws_authenticate(request))

        self.assertEqual(authenticated_request.endpoint, request.endpoint)
        self.assertEqual(authenticated_request.payload, request.payload)

    @patch("hummingbot.connector.exchange.derive.derive_auth.DeriveAuth.header_for_authentication")
    async def test_rest_authenticate(self, mock_header_for_auth):
        mock_header_for_auth.return_value = {"header": "value"}

        request = RESTRequest(
            method=RESTMethod.POST, url="/test", data=json.dumps({"key": "value"}), headers={}
        )
        authenticated_request = await (self.auth.rest_authenticate(request))

        self.assertIn("header", authenticated_request.headers)
        self.assertEqual(authenticated_request.headers["header"], "value")
        self.assertEqual(authenticated_request.data, json.dumps({"key": "value"}))

    def test_add_auth_to_params_post(self):
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

        with patch("hummingbot.connector.exchange.derive.derive_auth.SignedAction.sign") as mock_sign, \
                patch("hummingbot.connector.exchange.derive.derive_web_utils.order_to_call") as mock_order_to_call:
            mock_order_to_call.return_value = params
            mock_sign.return_value = None

            updated_params = self.auth.add_auth_to_params_post(params, request)
            self.assertIsInstance(updated_params, str)

    @patch("hummingbot.connector.exchange.derive.derive_auth.DeriveAuth.utc_now_ms")
    def test_get_ws_auth_payload(self, mock_utc_now):
        mock_utc_now.return_value = 1234567890
        mock_signature = "0x123signature"

        mock_account = MagicMock()
        mock_account.sign_message.return_value.signature.to_0x_hex.return_value = mock_signature
        self.auth._w3.eth.account = mock_account

        payload = self.auth.get_ws_auth_payload()

        self.assertEqual(payload["accept"], "application/json")
        self.assertEqual(payload["wallet"], self.api_key)
        self.assertEqual(payload["timestamp"], "1234567890")
        self.assertEqual(payload["signature"], mock_signature)

    @patch("hummingbot.connector.exchange.derive.derive_auth.DeriveAuth.utc_now_ms")
    def test_utc_now_ms(self, mock_utc_now):
        mock_utc_now.return_value = 1234567890
        timestamp = self.auth.utc_now_ms()
        self.assertEqual(timestamp, 1234567890)
