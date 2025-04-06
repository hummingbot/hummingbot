import unittest

from xrpl.constants import CryptoAlgorithm

from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth


class TestXRPLAuth(unittest.TestCase):
    def setUp(self):
        self.xrpl_secret_key = "sEdTvpec3RNNWwphd1WKZqt5Vs6GEFu"  # noqa: mock
        self.xrpl_auth = XRPLAuth(self.xrpl_secret_key)

    def test_get_account(self):
        account = self.xrpl_auth.get_account()
        # Replace 'expected_account' with the expected account string
        expected_account = "rfWRtDsi2M5bTxKtxpEmwpp81H8NAezwkw"  # noqa: mock
        self.assertEqual(account, expected_account)

    def test_get_algorithm(self):
        algorithm = self.xrpl_auth.get_algorithm(self.xrpl_secret_key)
        self.assertEqual(algorithm, CryptoAlgorithm.ED25519)
