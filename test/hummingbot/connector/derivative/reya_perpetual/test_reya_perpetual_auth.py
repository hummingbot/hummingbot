import json
import unittest
from decimal import Decimal
from pathlib import Path

from hummingbot.connector.derivative.reya_perpetual import reya_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_auth import (
    ReyaPerpetualAuth,
    scale_e18,
    wire_client_id,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

# Golden signatures from Reya's Python SDK parity tests, signed for the devnet gateway.
VECTORS = json.loads(Path(__file__).with_name("signatures.json").read_text())


class ReyaPerpetualAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.assertEqual(VECTORS["CHAIN_ID"], CONSTANTS.CHAIN_IDS[CONSTANTS.TESTNET_DOMAIN])
        self.assertEqual(VECTORS["ORDERS_GATEWAY"], CONSTANTS.ORDERS_GATEWAYS[CONSTANTS.TESTNET_DOMAIN])
        self.auth = ReyaPerpetualAuth(VECTORS["PRIVATE_KEY"], {"ETHRUSDPERP": 1}, CONSTANTS.TESTNET_DOMAIN)

    def test_signatures_match_the_sdk(self):
        order = {"accountId": 12345, "symbol": "ETHRUSDPERP", "exchangeId": 2, "orderType": "LIMIT", "isBuy": True,
                 "qty": "0.5", "limitPx": "3000", "timeInForce": "IOC", "clientOrderId": "42",
                 "nonce": "1700000000000000", "deadline": 1745000000}
        for name, changes in [("order", {}), ("order_sell", {"isBuy": False}), ("order_post_only", {"postOnly": True})]:
            signed = self.auth.sign_payload("createOrder", {**order, **changes})
            self.assertEqual(VECTORS["EXPECTED_SIGNATURES"][name], signed["signature"])
        cancel = {"accountId": 12345, "symbol": "ETHRUSDPERP", "orderId": "63552420354981888",
                  "nonce": "1700000000000001", "deadline": 1745000060}
        self.assertEqual(VECTORS["EXPECTED_SIGNATURES"]["order_cancel"],
                         self.auth.sign_payload("cancelOrder", cancel)["signature"])
        mass_cancel = {"accountId": 12345, "nonce": "1700000000000002", "deadline": 1745000120}
        self.assertEqual(VECTORS["EXPECTED_SIGNATURES"]["mass_cancel"],
                         self.auth.sign_payload("cancelAll", mass_cancel)["signature"])

    def test_nonces_increase_and_client_ids_are_stable_uint64(self):
        self.assertLess(self.auth.nonce(), self.auth.nonce())
        self.assertEqual(wire_client_id("HBOT-1"), wire_client_id("HBOT-1"))
        self.assertNotEqual(wire_client_id("HBOT-1"), wire_client_id("HBOT-2"))
        self.assertTrue(0 < int(wire_client_id("HBOT-1")) < 2 ** 64)

    def test_scaling_is_exact(self):
        self.assertEqual(123456789012123456789012345678, scale_e18(Decimal("123456789012.123456789012345678")))
        for invalid in ("NaN", "-1", "0.0000000000000000001"):
            with self.assertRaises(ValueError):
                scale_e18(Decimal(invalid))

    async def test_only_posts_are_signed(self):
        post = RESTRequest(RESTMethod.POST, url="https://api.reya.xyz/v2/cancelAll", data=json.dumps({"accountId": 42}))
        self.assertEqual(132, len(json.loads((await self.auth.rest_authenticate(post)).data)["signature"]))
        get = RESTRequest(RESTMethod.GET, url="https://api.reya.xyz/v2/feeTiers")
        self.assertIs(get, await self.auth.rest_authenticate(get))
        self.assertIs(get, await self.auth.ws_authenticate(get))
        with self.assertRaises(ValueError):
            self.auth.sign_payload("unsupported", {"accountId": 42})
