import asyncio
from collections import OrderedDict
from typing import Awaitable, Dict, Mapping, Optional
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class BybitPerpetualAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = BybitPerpetualAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_auth_signature(self):
        params = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            params=params,
            throttler_limit_id="/api/endpoint"
        )
        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertEqual(request.headers["X-BAPI-API-KEY"], self.api_key)
        self.assertIsNotNone(request.headers["X-BAPI-TIMESTAMP"])
        sign_expected = self.auth._generate_rest_signature(request.headers["X-BAPI-TIMESTAMP"], request.method, request.params)
        self.assertEqual(request.headers["X-BAPI-SIGN"], sign_expected)

    def test_add_auth_params_to_get_request_without_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )
        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertEqual(request.headers["X-BAPI-API-KEY"], self.api_key)
        self.assertIsNone(request.params)
        self.assertIsNone(request.data)

    def test_add_auth_params_to_get_request_with_params(self):
        params = {
            "param_z": "value_param_z",
            "param_a": "value_param_a"
        }
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params=params,
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )

        params_expected = self._params_expected(request.params)
        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual(len(request.params), 2)
        self.assertEqual(params_expected['param_z'], request.params["param_z"])
        self.assertEqual(params_expected['param_a'], request.params["param_a"])

    def test_add_auth_params_to_post_request(self):
        params = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://bybit-mock/api/endpoint",
            data=params,
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )
        params_request = self._params_expected(request.data)

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual(params_request['param_z'], request.data["param_z"])
        self.assertEqual(params_request['param_a'], request.data["param_a"])

    def test_ws_auth(self):
        request = WSJSONRequest(payload={}, is_auth_required=True)
        ws_auth_msg = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        api_key = ws_auth_msg["args"][0]
        expires = ws_auth_msg["args"][1]
        signature = ws_auth_msg["args"][2]

        self.assertEqual(ws_auth_msg["op"], "auth")
        self.assertEqual(api_key, self.api_key)
        self.assertEqual(signature, self.auth._generate_ws_signature(expires))

    def _params_expected(self, request_params: Optional[Mapping[str, str]]) -> Dict:
        request_params = request_params if request_params else {}
        return OrderedDict(sorted(request_params.items(), key=lambda t: t[0]))
