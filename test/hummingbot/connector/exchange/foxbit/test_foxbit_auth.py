import asyncio
import hashlib
import hmac
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from hummingbot.connector.exchange.foxbit import (
    foxbit_constants as CONSTANTS,
    foxbit_utils as utils,
    foxbit_web_utils as web_utils,
)
from hummingbot.connector.exchange.foxbit.foxbit_auth import FoxbitAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


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
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        endpoint_url = web_utils.rest_endpoint_url(url)
        request = RESTRequest(url=url, endpoint_url=endpoint_url, method=RESTMethod.GET, data=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        timestamp = configured_request.headers['X-FB-ACCESS-TIMESTAMP']
        payload = '{}{}{}{}'.format(timestamp,
                                    request.method,
                                    request.endpoint_url,
                                    params)
        expected_signature = hmac.new(self._secret.encode("utf8"), payload.encode("utf8"), hashlib.sha256).digest().hex()
        self.assertEqual(self._api_key, configured_request.headers['X-FB-ACCESS-KEY'])
        self.assertEqual(expected_signature, configured_request.headers['X-FB-ACCESS-SIGNATURE'])

    def test_ws_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = FoxbitAuth(api_key=self._api_key, secret_key=self._secret, user_id=self._user_id, time_provider=mock_time_provider)
        header = utils.get_ws_message_frame(
            endpoint=CONSTANTS.WS_AUTHENTICATE_USER,
            msg_type=CONSTANTS.WS_MESSAGE_FRAME_TYPE["Request"],
            payload=auth.get_ws_authenticate_payload(),
        )
        subscribe_request: WSJSONRequest = WSJSONRequest(payload=web_utils.format_ws_header(header), is_auth_required=True)
        retValue = self.async_run_with_timeout(auth.ws_authenticate(subscribe_request))
        self.assertIsNotNone(retValue)
