import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from eth_abi import encode
from eth_account import Account as EthAccount
from eth_account.messages import encode_defunct
from eth_utils import keccak

from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_auth import (
    VestPerpetualAuth,
)
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
    WSJSONRequest,
)


class VestPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        # random 32-byte hex private key (for testing only)
        self.signing_private_key = (
            "0xec4509d25bbb3ee0bdda08e3d23f82f94c3e0916bd4e1dd195e19d3a48de63fb"
        )
        self.account_group = 0

        self.auth = VestPerpetualAuth(
            api_key=self.api_key,
            signing_private_key=self.signing_private_key,
            account_group=self.account_group,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        async def runner():
            return await asyncio.wait_for(coroutine, timeout)

        return asyncio.run(runner())

    def _sample_order(self):
        return {
            "time": 1683849600076,
            "nonce": 0,
            "symbol": "BTC-PERP",
            "isBuy": True,
            "size": "0.1000",
            "orderType": "LIMIT",
            "limitPrice": "30000.00",
            "reduceOnly": False,
        }

    @patch(
        "hummingbot.connector.derivative.vest_perpetual.vest_perpetual_auth.VestPerpetualAuth._generate_orders_signature"
    )
    def test_rest_authenticate_adds_headers_and_signature_for_orders(
        self, generate_sig_mock: MagicMock
    ):
        generate_sig_mock.return_value = "0xsignature"

        body = {
            "order": self._sample_order(),
            "recvWindow": 60000,
        }
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://server-prod.hz.vestmarkets.com/v2/orders",
            data=json.dumps(body),
            is_auth_required=True,
            throttler_limit_id="/orders",
            headers={},
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        # Headers
        self.assertEqual(self.api_key, request.headers.get("X-API-KEY"))
        self.assertEqual(
            f"restserver{self.account_group}", request.headers.get("xrestservermm")
        )

        # Signature added to body
        updated_body = json.loads(request.data)
        self.assertEqual("0xsignature", updated_body.get("signature"))
        generate_sig_mock.assert_called_once_with(self._sample_order())

    def test_generate_orders_signature_recovers_signing_address(self):
        order = self._sample_order()

        # Signature produced by the auth helper
        signature = self.auth._generate_orders_signature(order)

        # Recompute args hash and recover address, as the server would
        args_hash = keccak(
            encode(
                [
                    "uint256",
                    "uint256",
                    "string",
                    "string",
                    "bool",
                    "string",
                    "string",
                    "bool",
                ],
                [
                    order["time"],
                    order["nonce"],
                    order["orderType"],
                    order["symbol"],
                    order["isBuy"],
                    order["size"],
                    order["limitPrice"],
                    order["reduceOnly"],
                ],
            )
        )
        signable_msg = encode_defunct(args_hash)
        recovered_addr = EthAccount.recover_message(signable_msg, signature=signature)

        expected_addr = EthAccount.from_key(self.signing_private_key).address
        self.assertEqual(expected_addr, recovered_addr)

    def test_ws_authenticate_is_pass_through(self):
        payload = {"one": "1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        result = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertIs(result, request)
        self.assertEqual(payload, result.payload)
