import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.lambdaplex import lambdaplex_constants as CONSTANTS
from hummingbot.connector.exchange.lambdaplex.lambdaplex_auth import LambdaplexAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class LambdaplexAuthTests(TestCase):
    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._private_key = "MC4CAQAwBQYDK2VwBCIEIJETIXjnIFeh11KAJZVv45sLhH8gCrWbL902cBfzCHE3"  # noqa: invalidated

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_post_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        data = {
            "symbol": "COINALPHA-HBOT",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": 0.1,
        }

        auth = LambdaplexAuth(api_key=self._api_key, private_key=self._private_key, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.POST, data=json.dumps(data), is_auth_required=True)
        configured_request = self.async_run_with_timeout(coroutine=auth.rest_authenticate(request=request))

        expected_params = {
            "symbol": "COINALPHA-HBOT",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": 0.1,
            "recvWindow": 5000,
            "timestamp": 1234567890000,
            "signature": "GS+fJUXk9pjSy6aSlWTjifeY0tiDHskJvU5aKSAhCwW0H4OwO+6tQs8D0gzOstbfbqXytldeSZvicvq9Zvs9CQ==",
        }

        self.assertEqual(expected_params, configured_request.params)
        self.assertEqual({"X-API-KEY": self._api_key}, configured_request.headers)

    def test_rest_delete_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        params = {
            "symbol": "COINALPHA-HBOT",
            "origClientOrderId": "1",
        }

        auth = LambdaplexAuth(api_key=self._api_key, private_key=self._private_key, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.DELETE, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(coroutine=auth.rest_authenticate(request=request))

        self.assertEqual("COINALPHA-HBOT", configured_request.params["symbol"])
        self.assertEqual("1", configured_request.params["origClientOrderId"])
        self.assertEqual(5000, configured_request.params["recvWindow"])
        self.assertEqual(1234567890000, configured_request.params["timestamp"])
        self.assertEqual(
            "kBnh8DMwdJ1DDlmdLxSMyEsyyWf0Rvh0RsT40G+CRxYFDvOgUGF4iBHKMZJEBQyiy2qoAKBQ6GPZ5lt2EEpWAw==",
            configured_request.params["signature"],
        )
        self.assertEqual({"X-API-KEY": self._api_key}, configured_request.headers)

    def test_rest_get_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        params = {"omitZeroBalances": True}

        auth = LambdaplexAuth(api_key=self._api_key, private_key=self._private_key, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(coroutine=auth.rest_authenticate(request=request))

        self.assertEqual(True, configured_request.params["omitZeroBalances"])
        self.assertEqual(5000, configured_request.params["recvWindow"])
        self.assertEqual(1234567890000, configured_request.params["timestamp"])
        self.assertEqual(
            "MtKBw3pFM/Rbw5kmwEeux6L0DlJG1g0EcyNCbc/gc6XYFYbxfe6c0OrxL+6IT7WllJIGZN3MfmfxXG0l+4iXAQ==",
            configured_request.params["signature"],
        )
        self.assertEqual({"X-API-KEY": self._api_key}, configured_request.headers)

    def test_ws_session_logon_method_auth(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        payload = {
            "id": 1,
            "method": CONSTANTS.WS_SESSION_LOGON_METHOD,
        }

        auth = LambdaplexAuth(api_key=self._api_key, private_key=self._private_key, time_provider=mock_time_provider)
        request = WSJSONRequest(payload=payload, is_auth_required=True)
        configured_request: WSJSONRequest = self.async_run_with_timeout(coroutine=auth.ws_authenticate(request=request))

        self.assertEqual(self._api_key, configured_request.payload["params"]["apiKey"])
        self.assertEqual(5000, configured_request.payload["params"]["recvWindow"])
        self.assertEqual(1234567890000, configured_request.payload["params"]["timestamp"])
        self.assertEqual(
            "t0JWo+U6NFKJZFt4j9IMbJ3soTZvrWbqrgNFAKp5ASY4RIgjaza8IsYJOCJgvtvCXTn3FIkKC2wyH7m0U3L3CQ==",
            configured_request.payload["params"]["signature"],
        )
