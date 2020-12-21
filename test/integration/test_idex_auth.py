#!/usr/bin/env python
import sys
import logging
import unittest

from os.path import join, realpath
from eth_account import Account

from hummingbot.connector.exchange.idex.idex_auth import IdexAuth
from hummingbot.core.event.events import OrderType, TradeType


sys.path.insert(0, realpath(join(__file__, "../../../")))


class IdexAuthUnitTest(unittest.TestCase):

    def test_get_signature(self):
        auth = IdexAuth(api_key="key_id", secret_key="key_secret")
        result = auth.generate_auth_dict(
            http_method="get",
            url="https://url.com/",
            params={"foo": "bar", "nonce": "2c1b41ae-0eeb-11eb-971f-0242ac110002"}
        )
        self.assertEqual(result["headers"]["IDEX-API-Key"], "key_id")
        self.assertEqual(
            result["headers"]["IDEX-HMAC-Signature"],
            "a55857025516a8b0f71ab80efeb5e15d5f52d48574c008b7663292eb1417d5bd"
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

    def test_wallet_signature(self):
        account = Account.from_key(
            "0xbae6890011b64ee26ee282692c8eef07330fd8ac101d2ae6cfa6acd30f940d01"
        )

        nonce = "cf7989e0-2030-11eb-8473-f1ca5eaaaff1"
        signature = IdexAuth.wallet_signature(
            ("uint128", IdexAuth.hex_to_uint128(nonce)),
            ("address", account.address),
            private_key=account.privateKey
        )

        self.assertEqual(
            signature,
            "0x42c474e4d58070c9be966ab925d0370b8e5ff4c5fd9ab623382b15262de2956e"
            "02e0a11b721edc26896134fd87fec71dd5e0cb6ada7ad2d5b004ac8dc32eb8071c"
        )

    def test_post_signature(self):
        auth = IdexAuth(api_key="key_id", secret_key="key_secret")
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
            "8829de6a69590fe5311d27370a848f6dbc230137bc4f9aadd7f8c633770a77d3"
        )
        self.assertIn("nonce", result["body"])


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
