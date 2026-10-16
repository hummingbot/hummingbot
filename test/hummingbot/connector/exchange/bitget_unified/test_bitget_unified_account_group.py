import unittest

from hummingbot.connector.derivative.bitget_unified_perpetual.bitget_unified_perpetual_derivative import (
    BitgetUnifiedPerpetualDerivative,
)
from hummingbot.connector.exchange.bitget_unified.bitget_unified_exchange import BitgetUnifiedExchange

API_KEY = "test_api_key"
SECRET_KEY = "test_secret_key"
PASSPHRASE = "test_passphrase"


class BitgetUnifiedAccountGroupTests(unittest.TestCase):
    """
    Bitget's UTA is one cross-margined wallet read by both connectors, so both report the same
    funds. They advertise a shared account id to stop that wallet being counted twice.
    """

    @staticmethod
    def _spot(api_key=API_KEY):
        return BitgetUnifiedExchange(
            bitget_unified_api_key=api_key,
            bitget_unified_secret_key=SECRET_KEY,
            bitget_unified_passphrase=PASSPHRASE,
            trading_pairs=["BTC-USDT"],
            trading_required=False,
        )

    @staticmethod
    def _perpetual(api_key=API_KEY):
        return BitgetUnifiedPerpetualDerivative(
            bitget_unified_perpetual_api_key=api_key,
            bitget_unified_perpetual_secret_key=SECRET_KEY,
            bitget_unified_perpetual_passphrase=PASSPHRASE,
            trading_pairs=["BTC-USDT"],
            trading_required=False,
        )

    def test_both_connectors_share_an_account_id_for_the_same_key(self):
        self.assertEqual(self._spot().account_group_id, self._perpetual().account_group_id)

    def test_different_api_keys_are_different_accounts(self):
        self.assertNotEqual(
            self._spot().account_group_id,
            self._spot(api_key="a_different_api_key").account_group_id,
        )

    def test_the_api_key_is_not_recoverable_from_the_id(self):
        group_id = self._spot().account_group_id

        self.assertNotIn(API_KEY, group_id)
        self.assertTrue(group_id.startswith("bitget_uta:"))

    def test_no_account_id_without_credentials(self):
        """The rate source builds connectors with no keys; they hold no account to group."""
        self.assertIsNone(self._spot(api_key="").account_group_id)


if __name__ == "__main__":
    unittest.main()
