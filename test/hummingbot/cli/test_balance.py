import unittest
from decimal import Decimal

from hummingbot.cli.commands.balance import _render


def _sample():
    return {
        "kraken": {
            "assets": [
                {"asset": "BTC", "total": Decimal("0.5"), "available": Decimal("0.4"),
                 "value": Decimal("30000"), "allocated": "20%"},
                {"asset": "USDT", "total": Decimal("100"), "available": Decimal("100"),
                 "value": Decimal("100"), "allocated": "0%"},
            ],
            "allocated_total": Decimal("6000"),
            "usd_total": Decimal("30100"),
        },
    }


class BalanceRenderTest(unittest.TestCase):
    def test_render_markdown_table_totals_and_grand_total(self):
        text = _render(_sample(), "$")
        self.assertIn("## kraken", text)                       # per-connector heading
        self.assertIn("| asset | total | value($) | allocated |", text)  # Markdown table header
        self.assertIn("BTC", text)
        self.assertIn("balances: $", text)                     # per-connector balances line
        self.assertIn("allocated:", text)                      # allocated % line
        self.assertIn("connectors total (net): $", text)       # grand total line

    def test_render_empty_exchange(self):
        result = {"kraken": {"assets": [], "allocated_total": Decimal("0"), "usd_total": Decimal("0")}}
        text = _render(result, "$")
        self.assertIn("## kraken", text)
        self.assertIn("_(no balance)_", text)

    def test_render_units_only_hides_value_and_grand_total(self):
        text = _render(_sample(), "$", units_only=True)
        self.assertIn("| asset | total | available |", text)   # units-only columns
        self.assertNotIn("value($)", text)                     # no USD value column
        self.assertNotIn("connectors total", text)             # no grand total when priceless


if __name__ == "__main__":
    unittest.main()
