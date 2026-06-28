import unittest
from decimal import Decimal

from hummingbot.cli.commands.balance import _nonzero


class BalanceHelperTest(unittest.TestCase):
    def test_filters_zero_balances(self):
        total = {"BTC": Decimal("0.5"), "USDT": Decimal("0"), "ETH": Decimal("2")}
        available = {"BTC": Decimal("0.4"), "ETH": Decimal("2")}
        out = _nonzero(total, available)
        self.assertEqual(set(out.keys()), {"BTC", "ETH"})  # zero USDT dropped
        self.assertEqual(out["BTC"], {"total": 0.5, "available": 0.4})

    def test_available_defaults_to_zero_when_missing(self):
        out = _nonzero({"SOL": Decimal("3")}, {})
        self.assertEqual(out["SOL"], {"total": 3.0, "available": 0.0})


if __name__ == "__main__":
    unittest.main()
