import unittest
from unittest.mock import MagicMock

from hummingbot.user.user_balances import UserBalances


class UserBalancesAccountGroupTests(unittest.TestCase):
    """
    A unified-account venue exposes one wallet through several connectors, each reporting it in
    full. Anything summing across connectors has to count that wallet once.
    """

    def setUp(self) -> None:
        super().setUp()
        self.user_balances = UserBalances.instance()
        self._original_markets = self.user_balances._markets
        self.user_balances._markets = {}

    def tearDown(self) -> None:
        self.user_balances._markets = self._original_markets
        super().tearDown()

    @staticmethod
    def _connector(group_id):
        connector = MagicMock()
        connector.account_group_id = group_id
        return connector

    def test_connectors_sharing_an_account_are_reported_as_duplicates(self):
        self.user_balances._markets = {
            "bitget_unified": self._connector("bitget_uta:abc123"),
            "bitget_unified_perpetual": self._connector("bitget_uta:abc123"),
        }

        duplicates = self.user_balances.duplicate_account_sources(
            ["bitget_unified", "bitget_unified_perpetual"]
        )

        # The first connector holds the account; the second merely repeats it.
        self.assertEqual({"bitget_unified_perpetual": "bitget_unified"}, duplicates)

    def test_different_credentials_are_never_folded_together(self):
        """Two API keys are two real accounts, even on the same venue."""
        self.user_balances._markets = {
            "bitget_unified": self._connector("bitget_uta:abc123"),
            "bitget_unified_perpetual": self._connector("bitget_uta:different"),
        }

        self.assertEqual(
            {},
            self.user_balances.duplicate_account_sources(
                ["bitget_unified", "bitget_unified_perpetual"]
            ),
        )

    def test_ordinary_connectors_are_untouched(self):
        self.user_balances._markets = {
            "binance": self._connector(None),
            "kucoin": self._connector(None),
        }

        self.assertEqual({}, self.user_balances.duplicate_account_sources(["binance", "kucoin"]))

    def test_connector_without_the_property_is_treated_as_standalone(self):
        """Cython connectors do not inherit ExchangePyBase, so the attribute may be absent."""
        self.user_balances._markets = {"legacy": object()}

        self.assertIsNone(self.user_balances.account_group_id("legacy"))
        self.assertEqual({}, self.user_balances.duplicate_account_sources(["legacy"]))

    def test_unknown_connector_has_no_group(self):
        self.assertIsNone(self.user_balances.account_group_id("never_added"))

    def test_the_first_connector_in_display_order_keeps_the_balance(self):
        """Whichever is shown first owns the total, so the displayed sum stays stable."""
        self.user_balances._markets = {
            "bitget_unified": self._connector("bitget_uta:abc123"),
            "bitget_unified_perpetual": self._connector("bitget_uta:abc123"),
        }

        reversed_order = self.user_balances.duplicate_account_sources(
            ["bitget_unified_perpetual", "bitget_unified"]
        )

        self.assertEqual({"bitget_unified": "bitget_unified_perpetual"}, reversed_order)


if __name__ == "__main__":
    unittest.main()
