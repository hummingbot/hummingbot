import unittest
from decimal import Decimal

from hummingbot.cli.commands.balance import _render, _to_json


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
    def test_to_json_totals_and_pct(self):
        out = _to_json(_sample(), "$")
        self.assertTrue(out["ok"])
        self.assertEqual(out["global_token"], "$")
        self.assertEqual(out["total_value"], 30100.0)
        ex = out["exchanges"]["kraken"]
        self.assertEqual(ex["total_value"], 30100.0)
        # allocated_pct = allocated_total / usd_total
        self.assertAlmostEqual(ex["allocated_pct"], 6000.0 / 30100.0, places=6)
        self.assertEqual(ex["assets"][0]["asset"], "BTC")
        self.assertEqual(ex["assets"][0]["value"], 30000.0)

    def test_to_json_zero_total_no_divide_by_zero(self):
        result = {"empty": {"assets": [], "allocated_total": Decimal("0"), "usd_total": Decimal("0")}}
        out = _to_json(result, "$")
        self.assertEqual(out["exchanges"]["empty"]["allocated_pct"], 0.0)
        self.assertEqual(out["total_value"], 0.0)

    def test_render_has_exchange_table_and_grand_total(self):
        text = _render(_sample(), "$")
        self.assertIn("kraken:", text)
        self.assertIn("Asset", text)
        self.assertIn("Allocated", text)
        self.assertIn("Total: $", text)          # per-exchange total line
        self.assertIn("Exchanges Total: $", text)  # grand total line

    def test_render_empty_exchange(self):
        result = {"kraken": {"assets": [], "allocated_total": Decimal("0"), "usd_total": Decimal("0")}}
        text = _render(result, "$")
        self.assertIn("You have no balance on this exchange.", text)


if __name__ == "__main__":
    unittest.main()
