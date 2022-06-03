import asyncio
import hashlib
import hmac
import unittest
from base64 import b64encode
from copy import copy
from datetime import datetime
from typing import Awaitable
from unittest.mock import patch

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_auth import CoinflexPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class CoinflexPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.auth = CoinflexPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_auth.CoinflexPerpetualAuth._time")
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

        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint="", params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))

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
            self.secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256).digest()).decode().strip()
        expected_headers = {
            "AccessKey": self.api_key,
            "Timestamp": str_timestamp,
            "Signature": expected_signature,
            "Nonce": str(nonce),
        }
        self.assertEqual(expected_headers, configured_request.headers)
