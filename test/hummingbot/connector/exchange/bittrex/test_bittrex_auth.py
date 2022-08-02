import asyncio
import hashlib
import hmac
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BittrexAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = BittrexAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_REST_authenticate(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )
        test_hash = self.auth.construct_content_hash({})
        test_sign_content = "".join(["1000000", "https://test.url/api/endpoint", "GET", test_hash, ""])
        expected_signature = hmac.new(self.secret_key.encode(), test_sign_content.encode(), hashlib.sha512).hexdigest()
        expected_timestamp = "1000000"

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual(self.api_key, request.headers["Api-Key"])
        self.assertEqual(expected_timestamp, request.headers["Api-Timestamp"])
        self.assertEqual(expected_signature, request.headers["Api-Signature"])

    @patch("uuid.uuid4")
    def test_WS_auth_params(self, mock_uuid):
        mock_uuid.return_value = "test"
        test_content = "1000test"
        test_signature = hmac.new(self.secret_key.encode(), test_content.encode(), hashlib.sha512).hexdigest()
        ret = self.auth.generate_WS_auth_params()
        self.assertIn(self.api_key, ret)
        self.assertIn(1000, ret)
        self.assertIn("test", ret)
        self.assertIn(test_signature, ret)
