import asyncio
from typing import Awaitable
from unittest import TestCase

import hummingbot.connector.exchange.vertex.vertex_constants as CONSTANTS
from hummingbot.connector.exchange.vertex.vertex_auth import VertexAuth
from hummingbot.connector.exchange.vertex.vertex_eip712_structs import Order
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class VertexAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        # NOTE: RANDOM KEYS GENERATED JUST FOR UNIT TESTS
        self.sender_address = "0x2162Db26939B9EAF0C5404217774d166056d31B5"  # noqa: mock
        self.private_key = "5500eb16bf3692840e04fb6a63547b9a80b75d9cbb36b43ca5662127d4c19c83"  # noqa: mock

        self.auth = VertexAuth(
            vertex_arbitrum_address=self.sender_address,
            vertex_arbitrum_private_key=self.private_key,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/api/endpoint",
        )
        ret = self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertEqual(request, ret)

    def test_ws_authenticate(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=False)
        ret = self.async_run_with_timeout(self.auth.ws_authenticate(request))
        self.assertEqual(payload, request.payload)
        self.assertEqual(request, ret)

    def test_get_referral_code_headers(self):
        headers = {"referer": CONSTANTS.HBOT_BROKER_ID}
        self.assertEqual(headers, self.auth.get_referral_code_headers())

    def test_sign_payload(self):
        order = Order(
            sender="0x2162Db26939B9EAF0C5404217774d166056d31B5",  # noqa: mock
            priceX18=26383000000000000000000,
            amount=2292000000000000000,
            expiration=1685989016166771694,
            nonce=1767924162661187978,
        )
        contract = "0xbf16e41fb4ac9922545bfc1500f67064dc2dcc3b"  # noqa: mock
        chain_id = "421613"
        expected_signature = "0x458cb49f9c20f3f2c8f57d229ca9f33fd23556b3d5c87dbe9366e9e09ef00c43632ef996f67434f55350a9241f4bff62da7055aaa889237d33e403b482e8abab1b"  # noqa: mock
        expected_digest = "0xaa4dadc6a1ed641eb46a22b1b58fd702e60392b8593e3fb29a5218f7f4010e69"  # noqa: mock
        signature, digest = self.auth.sign_payload(order, contract, chain_id)
        self.assertEqual(expected_signature, signature)
        self.assertEqual(expected_digest, digest)

    def test_generate_digest(self):
        signable_bytes = b"\x19\x01\xb0_\xd0\xc1Co\xf9K\xb2C$*S\x8f\xd78\xac\xc3\xdcdu\xf0\xfcY\x9d9\xac\xe7\xff/\xa6)\x1fp-\xfcL\x9d\xdf\xe8\xbb\xffe\x0bJIl\x14\x94\x89\xc9{\x9af\x97\xad2\x13\x8a1\xca\x89\xfa\xd3"  # noqa: mock
        expected_digest = "0xaa4dadc6a1ed641eb46a22b1b58fd702e60392b8593e3fb29a5218f7f4010e69"  # noqa: mock
        digest = self.auth.generate_digest(signable_bytes)
        self.assertEqual(expected_digest, digest)
