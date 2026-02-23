import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GRVTPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

class TestGRVTPerpetualAuth(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.api_secret = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318" # A random private key
        self.sub_account_id = "12345"
        self.auth = GRVTPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            sub_account_id=self.sub_account_id
        )

    @patch("aiohttp.ClientSession.post")
    def test_rest_authenticate(self, mock_post):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {
            "Set-Cookie": "gravity=test_cookie; expires=Wed, 21 Oct 2026 07:28:00 GMT",
            "X-Grvt-Account-Id": "account123"
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        request = RESTRequest(method=RESTMethod.GET, url="https://test.com")
        authenticated_request = asyncio.get_event_loop().run_until_complete(self.auth.rest_authenticate(request))

        self.assertIn("Cookie", authenticated_request.headers)
        self.assertEqual(authenticated_request.headers["Cookie"], "gravity=test_cookie")
        self.assertEqual(authenticated_request.headers["X-Grvt-Account-Id"], "account123")

    def test_sign_order_payload(self):
        message_data = {
            "subAccountID": 12345,
            "isMarket": False,
            "timeInForce": 1,
            "postOnly": True,
            "reduceOnly": False,
            "legs": [
                {
                    "assetID": int("0x123", 16),
                    "contractSize": 100000000,
                    "limitPrice": 50000000000,
                    "isBuyingContract": True
                }
            ],
            "nonce": 123456789,
            "expiration": 123456789000
        }
        
        signature = self.auth.sign_order_payload(message_data)
        self.assertIn("r", signature)
        self.assertIn("s", signature)
        self.assertIn("v", signature)
        self.assertIn("signer", signature)
        self.assertTrue(signature["r"].startswith("0x"))
        self.assertTrue(signature["s"].startswith("0x"))
