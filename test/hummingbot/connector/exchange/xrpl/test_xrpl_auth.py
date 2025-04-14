from unittest.async_case import IsolatedAsyncioTestCase

from xrpl.constants import CryptoAlgorithm

from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class TestXRPLAuth(IsolatedAsyncioTestCase):
    def setUp(self):
        # Test cases for different key formats
        self.ed25519_seed = "sEdTvpec3RNNWwphd1WKZqt5Vs6GEFu"  # noqa: mock
        self.secp256k1_seed = "snoPBrXtMeMyMHUVTgbuqAfg1SUTb"  # noqa: mock
        self.ed25519_private_key = "ED705389D8FB3E6CAA22F6D87533F9C47E86ECE224C2307BFEEFB56D96A71441FA"  # noqa: mock
        self.secp256k1_private_key = "001ACAAEDECE405B2A958212629E16F2EB46B153EEE94CDD350FDEFF52795525B7"  # noqa: mock

    def test_empty_secret_key(self):
        auth = XRPLAuth("")
        self.assertIsNotNone(auth.get_wallet())
        self.assertIsNotNone(auth.get_account())

    def test_ed25519_seed(self):
        auth = XRPLAuth(self.ed25519_seed)
        expected_account = "rfWRtDsi2M5bTxKtxpEmwpp81H8NAezwkw"  # noqa: mock
        self.assertEqual(auth.get_account(), expected_account)
        self.assertEqual(auth.get_algorithm(self.ed25519_seed), CryptoAlgorithm.ED25519)

    def test_secp256k1_seed(self):
        auth = XRPLAuth(self.secp256k1_seed)
        expected_account = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"  # noqa: mock
        self.assertEqual(auth.get_account(), expected_account)
        self.assertEqual(auth.get_algorithm(self.secp256k1_seed), CryptoAlgorithm.SECP256K1)

    def test_ed25519_private_key(self):
        auth = XRPLAuth(self.ed25519_private_key)
        expected_account = "rBWGigPacsJK2uBaGcJSZ3FJKxiRNipKcm"  # noqa: mock
        self.assertEqual(auth.get_account(), expected_account)

    def test_secp256k1_private_key(self):
        auth = XRPLAuth(self.secp256k1_private_key)
        expected_account = "rht63aedhW7g1cqbtDgMSLmGthyf4vZYrp"  # noqa: mock
        self.assertEqual(auth.get_account(), expected_account)

    def test_invalid_key_format(self):
        with self.assertRaises(ValueError) as context:
            XRPLAuth("invalid_key")
        self.assertIn("Invalid XRPL secret key format", str(context.exception))

    def test_get_wallet(self):
        auth = XRPLAuth(self.ed25519_seed)
        wallet = auth.get_wallet()
        self.assertIsNotNone(wallet)
        self.assertIsNotNone(wallet.public_key)
        self.assertIsNotNone(wallet.private_key)

    async def test_rest_authenticate(self):
        auth = XRPLAuth(self.ed25519_seed)
        request = RESTRequest(method=RESTMethod.GET, url="https://test.com")
        result = await auth.rest_authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(result, request)

    async def test_ws_authenticate(self):
        auth = XRPLAuth(self.ed25519_seed)
        request = WSJSONRequest(payload={})
        result = await auth.ws_authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(result, request)
