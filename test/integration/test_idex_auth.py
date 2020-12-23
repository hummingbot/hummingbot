#!/usr/bin/env python
import sys
import logging
import unittest

from os.path import join, realpath
from eth_account import Account

from hummingbot.connector.exchange.idex.idex_auth import IdexAuth
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.connector.exchange.idex.utils import create_nonce


sys.path.insert(0, realpath(join(__file__, "../../../")))


class IdexAuthUnitTest(unittest.TestCase):

    def test_get_signature(self):
        auth = IdexAuth(api_key="key_id", secret_key="key_secret", wallet_private_key="0x3952043cbb4217a5cf45e6518f40bfce245c6d8b227039c4102ab8a09dd9dbd8")
        result = auth.generate_auth_dict(
            http_method="get",
            url="https://url.com/",
            params={"foo": "bar", "nonce": "2c1b41ae-0eeb-11eb-971f-0242ac110002"}
        )
        self.assertEqual(result["headers"]["IDEX-API-Key"], "key_id")

        self.assertEqual(
            result["headers"]["IDEX-HMAC-Signature"],
            "32d603e2854a6d13c9b53b9abc612280871263ec6f0e5b64bc3e44502f4a9bbc"
        )
        self.assertIn("nonce", result["url"])

    def test_uint128_integration(self):
        for item in [
            "0x46c588f0-1f69-11eb-9714-fb733e326f68",
            "46c588f0-1f69-11eb-9714-fb733e326f68",
            "0x46c588f01f6911eb9714fb733e326f68"
        ]:
            uint128 = IdexAuth.hex_to_uint128(item)
            self.assertEqual(uint128, 0x46c588f01f6911eb9714fb733e326f68)

    def test_sign_message_string(self):
        wallet_private_key="0x3952043cbb4217a5cf45e6518f40bfce245c6d8b227039c4102ab8a09dd9dbd8"
        self._idex_auth = IdexAuth(api_key="key_id", secret_key="key_secret", wallet_private_key=wallet_private_key)
        orderVersion = 1
        market = "DIL-ETH"
        typeEnum = 0

        nonce = "91766796-4531-11eb-9669-30d16bd1b425"
        walletBytes = self._idex_auth.get_wallet_bytes()
        price = "0.20000000"
        sideEnum = 0
        amountEnum = 0  # base quantity
        amountString = "1.00000000"
        timeInForceEnum = 0
        selfTradePreventionEnum = 0

        byteArray = [
            IdexAuth.number_to_be(orderVersion, 1),
            bytes(nonce, 'utf-8'),
            IdexAuth.base16_to_binary(walletBytes),
            IdexAuth.encode(market),
            IdexAuth.number_to_be(typeEnum, 1),
            IdexAuth.number_to_be(sideEnum, 1),
            IdexAuth.encode(amountString),
            IdexAuth.number_to_be(amountEnum, 1),
            IdexAuth.encode(price),
            IdexAuth.encode(''),  # stopPrice
            IdexAuth.encode("abc123"),  # clientOrderId
            IdexAuth.number_to_be(timeInForceEnum, 1),
            IdexAuth.number_to_be(selfTradePreventionEnum, 1),
            IdexAuth.number_to_be(0, 8),  # unused
        ]

        binary = IdexAuth.binary_concat_array(byteArray)
        hash = IdexAuth.hash(binary, 'keccak', 'hex')
        signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.get_wallet(private_key=wallet_private_key).key))
        self.assertEqual(signature, "0xec305ed5ccde1789956eaec99dcac61955fcbef79e443535f0bd1485de1d2fe534c7287bb6cb3e2ae6c45490843dfec9b558437cd8aca32a7e1aa03f617caad21c")

    # def test_wallet_signature(self):
    #     account = Account.from_key(
    #         "0xbae6890011b64ee26ee282692c8eef07330fd8ac101d2ae6cfa6acd30f940d01"
    #     )

    #     nonce = "cf7989e0-2030-11eb-8473-f1ca5eaaaff1"
    #     signature = IdexAuth.wallet_signature(
    #         ("uint128", IdexAuth.hex_to_uint128(nonce)),
    #         ("address", account.address),
    #         private_key=account.privateKey
    #     )

    #     self.assertEqual(
    #         signature,
    #         "0x42c474e4d58070c9be966ab925d0370b8e5ff4c5fd9ab623382b15262de2956e"
    #         "02e0a11b721edc26896134fd87fec71dd5e0cb6ada7ad2d5b004ac8dc32eb8071c"
    #     )

    def test_post_signature(self):
        auth = IdexAuth(api_key="key_id", secret_key="key_secret", wallet_private_key="0x3952043cbb4217a5cf45e6518f40bfce245c6d8b227039c4102ab8a09dd9dbd8")
        result = auth.generate_auth_dict(
            http_method="post",
            url="https://url.com/",
            body={
                "parameters": {
                    "foo": "bar",
                    "nonce": "2c1b41ae-0eeb-11eb-971f-0242ac110002"
                }
            }
        )
        self.assertEqual(result["headers"]["IDEX-API-Key"], "key_id")
        self.assertEqual(
            result["headers"]["IDEX-HMAC-Signature"],
            "24efc46758e2bd21d9ce8589b0c247ff9d34d8a1df6e06d9c8837ef45f471346"
        )
        self.assertIn("nonce", result["body"])


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
