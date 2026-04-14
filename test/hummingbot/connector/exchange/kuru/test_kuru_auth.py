import unittest

from hummingbot.connector.exchange.kuru.kuru_auth import KuruAuth


class TestKuruAuth(unittest.TestCase):
    private_key = "0x0123456789012345678901234567890123456789012345678901234567890123"  # noqa: mock
    expected_address = "0x14791697260E4c9A71f18484C9f997B308e59325"

    def test_auth_derives_address_and_returns_wallet_config(self):
        auth = KuruAuth(self.private_key)

        self.assertEqual(self.expected_address, auth.address)
        self.assertEqual(self.private_key, auth.private_key)

        wallet_config = auth.get_wallet_config()
        self.assertEqual(self.private_key, wallet_config.private_key)
        self.assertEqual(self.expected_address, wallet_config.user_address)
