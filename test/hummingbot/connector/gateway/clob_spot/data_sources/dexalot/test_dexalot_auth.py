import asyncio
import unittest
from typing import Awaitable, TypeVar
from unittest.mock import MagicMock, patch

from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_auth import DexalotAuth, WalletSigner
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

T = TypeVar("T")


class DexalotAuthTest(unittest.TestCase):
    wallet_address: str
    wallet_private_key: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.wallet_address = "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18"  # noqa: mock

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable[T], timeout: int = 1) -> T:
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.wallet_sign")
    def test_rest_authenticate(self, wallet_sign_mock: MagicMock):
        signature = "someSignature"
        wallet_sign_mock.return_value = {"signature": signature}

        gateway_instance = GatewayHttpClient()
        signer = WalletSigner(
            chain="avalanche",
            network="dexalot",
            address=self.wallet_address,
            gateway_instance=gateway_instance,
        )
        auth = DexalotAuth(signer=signer, address=self.wallet_address)

        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://some.url.com",
        )
        authenticated_request = self.async_run_with_timeout(
            coroutine=auth.rest_authenticate(request=request)
        )

        expected_auth_headers = {"x-signature": f"{self.wallet_address}:{signature}"}

        self.assertEqual(expected_auth_headers, authenticated_request.headers)

        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://some.url.com",
            headers={"Content-Type": "application/json"},
        )
        authenticated_request = self.async_run_with_timeout(
            coroutine=auth.rest_authenticate(request=request)
        )

        expected_auth_headers = {
            "Content-Type": "application/json",
            "x-signature": f"{self.wallet_address}:{signature}",
        }

        self.assertEqual(expected_auth_headers, authenticated_request.headers)
