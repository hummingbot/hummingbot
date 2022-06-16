import asyncio
import hashlib
import hmac
from base64 import b64encode
from copy import copy
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from typing_extensions import Awaitable

from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.connector.exchange.coinflex.coinflex_web_utils import CoinflexRESTRequest
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class CoinflexAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "testSecret"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.exchange.coinflex.coinflex_auth.CoinflexAuth._time")
    def test_rest_authenticate(self, time_mock):
        now = 1234567890.000
        time_mock.return_value = now

        params = {
            "symbol": "LTCBTC",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": "0.1",
        }
        full_params = copy(params)

        auth = CoinflexAuth(api_key=self._api_key, secret_key=self._secret)
        request = CoinflexRESTRequest(method=RESTMethod.GET, endpoint="", params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        str_timestamp = datetime.utcfromtimestamp(now).isoformat()
        nonce = int(now * 1e3)

        encoded_params = "&".join([f"{key}={value}" for key, value in full_params.items()])
        payload = '{}\n{}\n{}\n{}\n{}\n{}'.format(str_timestamp,
                                                  nonce,
                                                  str(RESTMethod.GET),
                                                  request.auth_url,
                                                  request.auth_path,
                                                  encoded_params)

        expected_signature = b64encode(hmac.new(
            self._secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256).digest()).decode().strip()
        expected_headers = {
            "AccessKey": self._api_key,
            "Timestamp": str_timestamp,
            "Signature": expected_signature,
            "Nonce": str(nonce),
        }
        self.assertEqual(expected_headers, configured_request.headers)
