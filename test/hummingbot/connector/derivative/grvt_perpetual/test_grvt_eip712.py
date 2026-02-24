from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual.grvt_eip712 import (
    build_action_typed_data,
    sign_typed_action,
)


class GrvtEip712Tests(TestCase):
    def test_build_action_typed_data(self):
        typed = build_action_typed_data(
            account_address="0x1111111111111111111111111111111111111111",
            action_payload={"type": "order", "market": "BTC-USDC"},
            nonce=1700000000000,
        )
        self.assertEqual("Action", typed["primaryType"])
        self.assertEqual(1700000000000, typed["message"]["nonce"])

    def test_sign_typed_action(self):
        typed = build_action_typed_data(
            account_address="0x1111111111111111111111111111111111111111",
            action_payload={"type": "order"},
            nonce=1,
        )
        signed = sign_typed_action(
            private_key="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",
            typed_data=typed,
        )
        self.assertIn("signature", signed)
        self.assertIn("r", signed)
