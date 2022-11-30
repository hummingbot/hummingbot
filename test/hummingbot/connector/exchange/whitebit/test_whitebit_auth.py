import asyncio
import base64
import hashlib
import hmac
import json
from typing import Any, Awaitable, Dict, Optional, Tuple
from unittest import TestCase
from unittest.mock import MagicMock
from urllib.parse import urlparse

from hummingbot.connector.exchange.whitebit.whitebit_auth import WhitebitAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class WhitebitAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = WhitebitAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _create_payload_and_signature(self, url: str, request_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        all_params = request_data or {}

        parsed_url = urlparse(url)
        path_url = parsed_url.path

        all_params.update(
            {
                "request": path_url,
                "nonce": str(int(self.mock_time_provider.time() * 1e3)),
                "nonceWindow": True,
            }
        )

        data_json = json.dumps(all_params, separators=(",", ":"))  # use separators param for deleting spaces
        payload = base64.b64encode(data_json.encode("ascii"))
        signature = hmac.new(self.secret_key.encode("ascii"), payload, hashlib.sha512).hexdigest()

        string_payload = payload.decode("ascii")

        return string_payload, signature

    def test_add_auth_headers_to_get_request_without_params(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/api/endpoint",
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_payload, expected_signature = self._create_payload_and_signature(url=request.url)

        self.assertEqual(self.api_key, request.headers["X-TXC-APIKEY"])
        self.assertEqual(expected_payload, request.headers["X-TXC-PAYLOAD"])
        self.assertEqual(expected_signature, request.headers["X-TXC-SIGNATURE"])

        expected_request_data = {
            "request": "/api/endpoint",
            "nonce": str(int(self.mock_time_provider.time() * 1e3)),
            "nonceWindow": True,
        }
        self.assertEqual(expected_request_data, json.loads(request.data))

    def test_add_auth_headers_to_get_request_with_params(self):
        request_data = {"ticker": "BTC"}

        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/endpoint",
            data=json.dumps(request_data),
            is_auth_required=True,
            throttler_limit_id="/api/endpoint",
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_payload, expected_signature = self._create_payload_and_signature(
            url=request.url, request_data=request_data
        )

        self.assertEqual(self.api_key, request.headers["X-TXC-APIKEY"])
        self.assertEqual(expected_payload, request.headers["X-TXC-PAYLOAD"])
        self.assertEqual(expected_signature, request.headers["X-TXC-SIGNATURE"])

        expected_request_data = {
            "ticker": "BTC",
            "request": "/api/endpoint",
            "nonce": str(int(self.mock_time_provider.time() * 1e3)),
            "nonceWindow": True,
        }
        self.assertEqual(expected_request_data, json.loads(request.data))

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)
