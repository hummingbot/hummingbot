import base64
import hashlib
import hmac
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.bitget.bitget_auth import BitgetAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class BitgetAuthTests(IsolatedAsyncioWrapperTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.secret_key = "test_secret_key"
        self.passphrase = "test_passphrase"
        self._time_synchronizer_mock = MagicMock()
        self._time_synchronizer_mock.time.return_value = 1640001112.223

        self.auth = BitgetAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.passphrase,
            time_provider=self._time_synchronizer_mock)

    def _sign(self, payload: str) -> str:
        return base64.b64encode(
            hmac.new(self.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
        ).decode().strip()

    async def test_add_auth_to_get_request(self) -> None:
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.bitget.com/api/v3/trade/order-info",
            throttler_limit_id="/api/v3/trade/order-info",
            params={"clientOid": "1", "category": "SPOT"},
            is_auth_required=True,
            headers={},
        )

        await self.auth.rest_authenticate(request)

        timestamp = request.headers["ACCESS-TIMESTAMP"]
        self.assertAlmostEqual(self._time_synchronizer_mock.time(), int(timestamp) * 1e-3, places=2)
        self.assertEqual(self.api_key, request.headers["ACCESS-KEY"])
        self.assertEqual(self.passphrase, request.headers["ACCESS-PASSPHRASE"])
        self.assertEqual(
            self._sign(f"{timestamp}GET/api/v3/trade/order-info?clientOid=1&category=SPOT"),
            request.headers["ACCESS-SIGN"],
        )
        self.assertEqual({"clientOid": "1", "category": "SPOT"}, request.params)

    async def test_add_auth_to_post_request_signs_the_body(self) -> None:
        body = json.dumps({"clientOid": "1"})
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.bitget.com/api/v3/trade/cancel-order",
            throttler_limit_id="/api/v3/trade/cancel-order",
            data=body,
            is_auth_required=True,
            headers={},
        )

        await self.auth.rest_authenticate(request)

        timestamp = request.headers["ACCESS-TIMESTAMP"]
        self.assertEqual(
            self._sign(f"{timestamp}POST/api/v3/trade/cancel-order{body}"),
            request.headers["ACCESS-SIGN"],
        )

    async def test_signature_uses_the_request_path_not_the_throttler_limit_id(self) -> None:
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.bitget.com/api/v3/trade/fills",
            throttler_limit_id="shared-trade-bucket",
            params={"orderId": "123"},
            is_auth_required=True,
            headers={},
        )

        await self.auth.rest_authenticate(request)

        timestamp = request.headers["ACCESS-TIMESTAMP"]
        self.assertEqual(
            self._sign(f"{timestamp}GET/api/v3/trade/fills?orderId=123"),
            request.headers["ACCESS-SIGN"],
        )

    def test_ws_auth_payload(self) -> None:
        payload = self.auth.get_ws_auth_payload()

        timestamp = str(int(self._time_synchronizer_mock.time()))
        self.assertEqual(self.api_key, payload["apiKey"])
        self.assertEqual(self.passphrase, payload["passphrase"])
        self.assertEqual(timestamp, payload["timestamp"])
        self.assertEqual(self._sign(f"{timestamp}GET/user/verify"), payload["sign"])

    async def test_no_auth_added_to_ws_request(self) -> None:
        payload = {"one": "1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        await self.auth.ws_authenticate(request)

        self.assertEqual(payload, request.payload)
