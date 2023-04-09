import asyncio
import base64
import hashlib
import hmac
import time
import unittest
from copy import copy
from datetime import datetime
from unittest.mock import MagicMock
from urllib.parse import urlencode

from typing_extensions import Awaitable

from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HuobiAuthTests(unittest.TestCase):

    def setUp(self):
        self._api_key = "testApiKey"
        self._secret = "testSecret"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = time.time()
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now
        now = datetime.utcfromtimestamp(now).strftime("%Y-%m-%dT%H:%M:%S")
        test_url = "https://api.huobi.pro/v1/order/openOrders"
        params = {
            "order-id": "EO1D1",
        }
        full_params = copy(params)

        auth = HuobiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, url=test_url, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        full_params.update({"Timestamp": now,
                            "AccessKeyId": self._api_key,
                            "SignatureMethod": "HmacSHA256",
                            "SignatureVersion": "2"
                            })
        full_params = HuobiAuth.keysort(full_params)
        encoded_params = urlencode(full_params)
        payload = "\n".join(["GET", "api.huobi.pro", "/v1/order/openOrders", encoded_params])
        test_digest = hmac.new(
            self._secret.encode("utf8"),
            payload.encode("utf8"),
            hashlib.sha256).digest()
        expected_signature = base64.b64encode(test_digest).decode()
        self.assertEqual(now, configured_request.params["Timestamp"])
        self.assertEqual(expected_signature, configured_request.params["Signature"])
