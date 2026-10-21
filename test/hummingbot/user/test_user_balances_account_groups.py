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


class SharedAccountTotalsTests(unittest.TestCase):
    """
    Only the wallet is shared between connectors on one account. Positions belong to whichever
    connector holds them, so their unrealized PnL must survive the deduplication.
    """

    @staticmethod
    def _result():
        from decimal import Decimal
        asset = {"asset": "USDT", "total": Decimal("88.93"), "available": Decimal("88.93"),
                 "value": Decimal("88.93"), "allocated": "0%"}
        return {
            "bitget_unified": {
                "assets": [asset], "allocated_total": Decimal("0"), "usd_total": Decimal("93.35"),
            },
            "bitget_unified_perpetual": {
                "assets": [asset], "allocated_total": Decimal("0"), "usd_total": Decimal("93.35"),
                "pnl_total": Decimal("5"),
                "positions": [{"trading_pair": "XRP-USDC", "side": "LONG", "amount": "10",
                               "entry_price": "1.5", "notional": "15",
                               "unrealized_pnl": "5", "leverage": "3"}],
                "duplicate_of": "bitget_unified",
            },
        }

    def test_rendered_total_keeps_the_duplicates_unrealized_pnl(self):
        import hummingbot.cli.commands.balance as balance_cli

        rendered = balance_cli._render(self._result(), "$")
        total_line = next(ln for ln in rendered.splitlines() if "connectors total" in ln)

        # $93.35 wallet counted once, plus the $5 PnL that only the perpetual connector holds.
        self.assertIn("98.35", total_line)

    def test_json_total_matches_the_rendered_total(self):
        import hummingbot.cli.commands.balance as balance_cli

        payload = balance_cli._json_payload(self._result(), "USDT", units_only=False)

        # The JSON path used to sum every connector, inflating the total past the rendered one.
        self.assertEqual(98.35, payload["net_value_total"])
        self.assertEqual("bitget_unified", payload["connectors"]["bitget_unified_perpetual"]["duplicate_of"])
