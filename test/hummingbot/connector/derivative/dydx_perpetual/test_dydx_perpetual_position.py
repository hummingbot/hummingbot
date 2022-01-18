import unittest
from decimal import Decimal

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_position import DydxPerpetualPosition
from hummingbot.core.event.events import PositionSide


class DydxPerpetualPositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def test_amount_always_positive_for_long_and_always_negative_for_short(self):
        p = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.LONG,
            unrealized_pnl=Decimal("10"),
            entry_price=Decimal("2"),
            amount=Decimal("1"),
            leverage=Decimal("10"),
        )

        self.assertEqual(Decimal("1"), p.amount)

        p = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.LONG,
            unrealized_pnl=Decimal("10"),
            entry_price=Decimal("2"),
            amount=Decimal("-1"),
            leverage=Decimal("10"),
        )

        self.assertEqual(Decimal("1"), p.amount)

        p = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.SHORT,
            unrealized_pnl=Decimal("10"),
            entry_price=Decimal("2"),
            amount=Decimal("1"),
            leverage=Decimal("10"),
        )

        self.assertEqual(Decimal("-1"), p.amount)

        p = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.SHORT,
            unrealized_pnl=Decimal("10"),
            entry_price=Decimal("2"),
            amount=Decimal("-1"),
            leverage=Decimal("10"),
        )

        self.assertEqual(Decimal("-1"), p.amount)

    def test_update_position(self):
        p = DydxPerpetualPosition(
            self.trading_pair,
            PositionSide.LONG,
            unrealized_pnl=Decimal("10"),
            entry_price=Decimal("2"),
            amount=Decimal("1"),
            leverage=Decimal("10"),
        )
        new_unrealized_pnl = Decimal("11")
        new_amount = Decimal("2")
        p.update_position(
            unrealized_pnl=new_unrealized_pnl,
            amount=new_amount,
            status="CLOSED",
        )

        self.assertEqual(new_unrealized_pnl, p.unrealized_pnl)
        self.assertEqual(new_amount, p.amount)
        self.assertFalse(p.is_open)
