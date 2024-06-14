import asyncio
import hashlib
import hmac
from collections import OrderedDict
from typing import Any, Awaitable, Dict, Mapping, Optional
from unittest import TestCase
from unittest.mock import MagicMock
from urllib.parse import urlencode

from hummingbot.connector.exchange.bing_x.bing_x_auth import BingXAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class BingXAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.auth = BingXAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_add_auth_params_to_get_request_without_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertIsNotNone(request.headers['X-BX-APIKEY'])
        self.assertIsNotNone(request.params['timestamp'])
        self.assertIsNotNone(request.params['signature'])

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
        self.assertIsNotNone(request.headers['X-BX-APIKEY'])
        self.assertIsNotNone(request.params['timestamp'])
        self.assertIsNotNone(request.params['signature'])
        self.assertEqual(params_expected['param_z'], request.params["param_z"])
        self.assertEqual(params_expected['param_a'], request.params["param_a"])

    def test_add_auth_params_to_post_request(self):
        params = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/endpoint",
            data=params,
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )
        params_auth = self._params_expected(request.params)
        params_request = self._params_expected(request.data)

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertIsNotNone(request.headers['X-BX-APIKEY'])
        self.assertIsNotNone(request.params['timestamp'])
        self.assertIsNotNone(request.params['signature'])
        self.assertEqual(params_request['param_z'], request.data["param_z"])
        self.assertEqual(params_request['param_a'], request.data["param_a"])

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)
        self.async_run_with_timeout(self.auth.ws_authenticate(request))
        self.assertEqual(payload, request.payload)

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        encoded_params_str = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"), encoded_params_str.encode("utf8"), hashlib.sha256).hexdigest()
        return digest

    def _params_expected(self, request_params: Optional[Mapping[str, str]]) -> Dict:
        request_params = request_params if request_params else {}
        params = {
            'timestamp': 1000000,
            'api_key': self.api_key,
        }
        params.update(request_params)
        params = OrderedDict(sorted(params.items(), key=lambda t: t[0]))
        params['sign'] = self._generate_signature(params=params)
        return params
