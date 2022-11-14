import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class DydxPerpetualAuthTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someApiKey"
        # Not a real secret key
        cls.api_secret = "AA1p9oklqBkDT8xw2FRWwlZCfUf98wEG"
        cls.passphrase = "somePassphrase"
        cls.ethereum_address = "someEthAddress"
        cls.stark_private_key = "0123456789"

    def setUp(self) -> None:
        super().setUp()
        self.auth = DydxPerpetualAuth(
            self.api_key, self.api_secret, self.passphrase, self.ethereum_address, self.stark_private_key
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth.DydxPerpetualAuth._get_iso_timestamp")
    def test_add_auth_to_rest_request(self, ts_mock: MagicMock):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params=params,
            data="{}",
            is_auth_required=True,
        )
        ts_mock.return_value = "2022-07-06T12:20:53.000Z"

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual("f9KTZzueyS1MazebIiorgGnZ5aOsVB3o7N2mRaW520g=", request.headers["DYDX-SIGNATURE"])
        self.assertEqual("someApiKey", request.headers["DYDX-API-KEY"])
        self.assertEqual(ts_mock.return_value, request.headers["DYDX-TIMESTAMP"])
        self.assertEqual("somePassphrase", request.headers["DYDX-PASSPHRASE"])

    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth.DydxPerpetualAuth._get_iso_timestamp")
    def test_add_auth_to_ws_request(self, ts_mock: MagicMock):
        ts_mock.return_value = "2022-07-06T12:20:53.000Z"

        request = WSJSONRequest(
            payload={"channel": CONSTANTS.WS_CHANNEL_ACCOUNTS},
            is_auth_required=True,
        )

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual("someApiKey", request.payload["apiKey"])
        self.assertEqual("somePassphrase", request.payload["passphrase"])
        self.assertEqual(ts_mock.return_value, request.payload["timestamp"])
        self.assertEqual("MLJvgJDWv-o1lz1e6oRuU96SbCay1Qo9m-E6kKleOxY=", request.payload["signature"])

    def test_get_order_signature(self):
        result = self.auth.get_order_signature(
            position_id="0123456789",
            client_id="someClientOrderId",
            market="BTC-USD",
            side="BUY",
            size="1",
            price="10",
            limit_fee="33",
            expiration_epoch_seconds=1000,
        )

        self.assertEqual(
            result,
            "0776f3b3427920efdfad8f5cff438621bebcea4c1a15763a3436119fd2f896680551f3e9d8ae48e45a328814"  # noqa: mock
            "d49370165e19ecd24e543071c81d53211950982f",
        )  # noqa: mock
