import asyncio
from unittest import TestCase

from typing_extensions import Awaitable

from hummingbot.connector.exchange.cube.cube_auth import CubeAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class CubeAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "1111111111-11111-11111-11111-1111111111"
        self._secret = "111111111111111111111111111111"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        params = {
            "symbol": "LTCBTC",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": "0.1",
        }

        auth = CubeAuth(api_key=self._api_key, secret_key=self._secret)
        request = RESTRequest(method=RESTMethod.GET, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        configured_headers = configured_request.headers
        configured_timestamp = configured_headers["x-api-timestamp"]
        configured_signature = configured_headers["x-api-signature"]
        configured_api_key = configured_headers["x-api-key"]

        self.assertEqual(configured_api_key, self._api_key)
        self.assertTrue(auth.verify_signature(configured_signature, int(configured_timestamp)))

        synthetic_timestamp = int(configured_timestamp) + 1
        generated_signature, used_timestamp = auth._generate_signature(synthetic_timestamp)
        self.assertTrue(auth.verify_signature(generated_signature, synthetic_timestamp))
        self.assertTrue(synthetic_timestamp == used_timestamp)
