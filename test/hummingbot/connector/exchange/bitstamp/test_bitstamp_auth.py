import asyncio
from unittest import TestCase
from unittest.mock import MagicMock
from urllib.parse import urlencode

from typing_extensions import Awaitable

from hummingbot.connector.exchange.bitstamp.bitstamp_auth import BitstampAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BitstampAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret_key = "testApiKey"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = BitstampAuth(api_key=self._api_key, secret_key=self._secret_key, time_provider=mock_time_provider)
        request = RESTRequest(url="https://www.test.com/url", method=RESTMethod.GET, is_auth_required=True, headers={})
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        self.assertEqual(f"BITSTAMP {self._api_key}", configured_request.headers["X-Auth"])
        self.assertEqual(auth.AUTH_VERSION, configured_request.headers["X-Auth-Version"])
        self.assertEqual(str(int(now * 1e3)), configured_request.headers["X-Auth-Timestamp"])
        self.assertIn("X-Auth-Nonce", configured_request.headers)
        self.assertIn("X-Auth-Signature", configured_request.headers)

    def test_generate_message(self):
        now = "1640000000000000"
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = float(now)

        nonce = "nonce"
        auth = BitstampAuth(self._api_key, self._secret_key, mock_time_provider)

        msg = auth._generate_message(RESTMethod.POST, "https://www.test.com/url", None, None, nonce, now)

        self.assertEqual(f"BITSTAMP {self._api_key}POSTwww.test.com/url{nonce}{now}{auth.AUTH_VERSION}", msg)

    def test_generate_message_with_payload(self):
        now = "1640000000000000"
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = float(now)

        nonce = "nonce"
        content_type = "application/x-www-form-urlencoded"
        payload = {"key": "value", "key2": "value2"}
        auth = BitstampAuth(self._api_key, self._secret_key, mock_time_provider)

        msg = auth._generate_message(RESTMethod.POST, "https://www.test.com/url", content_type, payload, nonce, now)

        self.assertEqual(f"BITSTAMP {self._api_key}POSTwww.test.com/url{content_type}{nonce}{now}{auth.AUTH_VERSION}{urlencode(payload)}", msg)
