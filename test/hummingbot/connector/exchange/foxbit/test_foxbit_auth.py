import asyncio
import hashlib
import hmac
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

import hummingbot.connector.exchange.foxbit.foxbit_constants as CONSTANTS
import hummingbot.connector.exchange.foxbit.foxbit_web_utils as webutil
from hummingbot.connector.exchange.foxbit.foxbit_auth import FoxbitAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class FoxbitAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "testSecret"
        self._user_id = "testUserId"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        params = {
            "symbol": "COINALPHAHBOT",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": "0.1",
        }

        auth = FoxbitAuth(api_key=self._api_key, secret_key=self._secret, user_id=self._user_id, time_provider=mock_time_provider)
        url = webutil.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        endpoint_url = webutil.rest_endpoint_url(url)
        request = RESTRequest(url=url, endpoint_url=endpoint_url, method=RESTMethod.GET, data=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        timestamp = configured_request.headers['X-FB-ACCESS-TIMESTAMP']
        payload = '{}{}{}{}'.format(timestamp,
                                    request.method,
                                    request.endpoint_url,
                                    params)
        expected_signature = hmac.new(self._secret.encode("utf8"), payload.encode("utf8"), hashlib.sha256).digest().hex()
        print(payload)

        self.assertEqual(self._api_key, configured_request.headers['X-FB-ACCESS-KEY'])
        self.assertEqual(expected_signature, configured_request.headers['X-FB-ACCESS-SIGNATURE'])
