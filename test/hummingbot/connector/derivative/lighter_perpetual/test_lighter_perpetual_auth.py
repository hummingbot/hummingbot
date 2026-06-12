import asyncio
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class MockSignerClient:
    def __init__(self):
        self.calls = 0

    def create_auth_token_with_expiry(self, deadline, api_key_index):
        self.calls += 1
        return f"token-{self.calls}", None


class LighterPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.signer_client = MockSignerClient()
        self.auth = LighterAuth(signer_client=self.signer_client, api_key_index=9)

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.run(asyncio.wait_for(coroutine, timeout))

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth.time.time")
    def test_rest_authenticate_adds_auth_header_and_param(self, time_mock):
        time_mock.return_value = 1000
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.lighter.xyz/account",
            headers={},
            params={"account_index": 1},
            is_auth_required=True,
        )

        authenticated_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual("token-1", authenticated_request.headers["authorization"])
        self.assertEqual("token-1", authenticated_request.params["auth"])
        self.assertEqual(1, self.signer_client.calls)

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth.time.time")
    def test_ws_authenticate_adds_auth_payload(self, time_mock):
        time_mock.return_value = 1000
        request = WSJSONRequest(payload={"type": "subscribe", "channel": "account_all_trades/1"})

        authenticated_request = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual("token-1", authenticated_request.payload["auth"])
        self.assertEqual(1, self.signer_client.calls)

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth.time.time")
    def test_get_auth_token_reuses_cached_token_before_refresh_window(self, time_mock):
        time_mock.side_effect = [1000, 1000, 1200]

        token_one = self.async_run_with_timeout(self.auth._get_auth_token())
        token_two = self.async_run_with_timeout(self.auth._get_auth_token())

        self.assertEqual("token-1", token_one)
        self.assertEqual(token_one, token_two)
        self.assertEqual(1, self.signer_client.calls)

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth.time.time")
    def test_get_auth_token_refreshes_when_expiring(self, time_mock):
        time_mock.side_effect = [1000, 1000, 1571, 1571]

        token_one = self.async_run_with_timeout(self.auth._get_auth_token())
        token_two = self.async_run_with_timeout(self.auth._get_auth_token())

        self.assertEqual("token-1", token_one)
        self.assertEqual("token-2", token_two)
        self.assertEqual(2, self.signer_client.calls)
