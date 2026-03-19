from decimal import Decimal
from unittest import TestCase

from hummingbot.strategy_v2.executors.progressive_executor.data_types import LadderedTrailingStop
from hummingbot.strategy_v2.utils.trailing_stop_manager import TrailingStopManager


class TestTrailingStopController(TestCase):
    def setUp(self):
        self.on_close_called = False
        self.partial_close_amount = Decimal("0")

        self.trailing_stop_config = LadderedTrailingStop(
            activation_pnl_pct=Decimal("0.02"),
            trailing_pct=Decimal("0.01"),
            take_profit_table=(
                (Decimal("0.05"), Decimal("0.5")),
                (Decimal("0.1"), Decimal("1")),  # At 10% PnL, close 100%
            ),
        )

        self.controller = TrailingStopManager(
            trailing_stop_config=self.trailing_stop_config,
            pnl_relaxation=Decimal("0.9"),
            max_trailing_pct=Decimal("0.05"),
        )

    def _on_close_position(self):
        self.on_close_called = True

    def _on_partial_close(self, amount: Decimal):
        self.partial_close_amount = amount

    def test_take_profit_table_lookup(self):
        """Tests how we find take profit levels in different scenarios."""
        # Initial lookup at 7% - should find 5% level
        takeprofit = self.controller._find_closest_take_profit(Decimal("0.07"))
        self.assertEqual(takeprofit, (Decimal("0.05"), Decimal("0.5")))

        # At 10% - should find 10% level
        takeprofit = self.controller._find_closest_take_profit(Decimal("0.10"))
        self.assertEqual(takeprofit, (Decimal("0.1"), Decimal("1")))

        # Drop from 10% to 5% - should find 5% level
        takeprofit = self.controller._find_closest_take_profit(Decimal("0.05"))
        self.assertEqual(takeprofit, (Decimal("0.05"), Decimal("0.5")))

        # Drop from 7% to 4% - should not find any level
        takeprofit = self.controller._find_closest_take_profit(Decimal("0.04"))
        self.assertEqual(takeprofit, (Decimal("0"), Decimal("1")))  # Default

        # Test exact matches
        takeprofit = self.controller._find_closest_take_profit(Decimal("0.05"))
        self.assertEqual(takeprofit, (Decimal("0.05"), Decimal("0.5")))

    def test_calculate_trailing_percentage(self):
        """Tests trailing percentage calculation step by step."""
        net_pnl = Decimal("0.025")  # 2.5%

        # Step by step calculation
        min_trailing = self.trailing_stop_config.trailing_pct
        print(f"Min trailing from config: {min_trailing}")  # Should be 0.01

        pnl_adjust = net_pnl * self.controller._pnl_relaxation
        print(f"Damped value: {pnl_adjust}")  # Should be 0.025 * 0.9 = 0.0225

        max_trailing = self.controller._max_trailing_pct
        print(f"Max trailing allowed: {max_trailing}")  # Should be 0.05

        # Test the actual calculation
        trailing_pct = self.controller._calculate_trailing_percentage(net_pnl)
        print(f"Calculated trailing: {trailing_pct}")

        # Verify which value was chosen
        expected = min(pnl_adjust + min_trailing, max_trailing)
        print(f"Expected trailing: {expected}")

        self.assertEqual(trailing_pct, expected)

    def test_trigger_pnl_updates(self):
        """Tests how the trigger PNL gets updated in different scenarios."""
        # Initial activation
        net_pnl_pct = Decimal("0.025")  # 2.5%
        self.controller.update(net_pnl_pct=net_pnl_pct, current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        first_trigger = self.controller.pnl_trigger
        self.assertEqual(net_pnl_pct - self.controller._calculate_trailing_percentage(Decimal("0.025")),
                         first_trigger)

        # Move up - should update trigger
        self.controller.update(net_pnl_pct=Decimal("0.035"), current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        second_trigger = self.controller.pnl_trigger
        self.assertGreater(second_trigger, first_trigger)

        # Small drop - should not update trigger
        self.controller.update(net_pnl_pct=Decimal("0.033"), current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        self.assertEqual(self.controller.pnl_trigger, second_trigger)

    def test_initial_activation(self):
        """Tests initial activation of trailing stop."""
        # Below activation threshold
        self.controller.update(
            net_pnl_pct=Decimal("0.01"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertIsNone(self.controller.pnl_trigger)
        self.assertFalse(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0"))

        # Above activation threshold
        self.controller.update(
            net_pnl_pct=Decimal("0.025"),  # 2.5%
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertEqual(
            Decimal("0.025") - self.controller._calculate_trailing_percentage(Decimal("0.025")),
            self.controller.pnl_trigger)  # 2.5% - 1%
        self.assertFalse(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0"))

    def test_trailing_stop_updates(self):
        """Tests trailing stop updates as price moves up."""
        # Initial activation
        self.controller.update(
            net_pnl_pct=Decimal("0.025"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        initial_trigger = self.controller.pnl_trigger

        # Price moves up
        self.controller.update(
            net_pnl_pct=Decimal("0.035"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertGreater(self.controller.pnl_trigger, initial_trigger)
        self.assertFalse(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0"))

    def test_partial_take_profit(self):
        """Tests partial take profit at first level."""
        # Move to first take profit level (5%)
        self.controller.update(
            net_pnl_pct=Decimal("0.1"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        # Drop below trigger
        self.controller.update(
            net_pnl_pct=Decimal("0.05"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertFalse(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0.5"))

    def test_full_take_profit(self):
        """Tests full position close at second level."""
        # Move to second take profit level (10%)
        self.controller.update(
            net_pnl_pct=Decimal("0.1"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        # Drop, but above trigger set at the max of 5%
        self.controller.update(
            net_pnl_pct=Decimal("0.08"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertFalse(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0"))
        # Drop below trigger set at the max of 5%
        self.controller.update(
            net_pnl_pct=Decimal("0.0499"),
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertTrue(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0"))

    def test_trailing_percentage_calculation(self):
        """Tests the dynamic trailing percentage calculation."""
        # Small PnL - should use config trailing_pct
        trailing_pct = self.controller._calculate_trailing_percentage(Decimal("0.01"))
        self.assertEqual(trailing_pct, self.trailing_stop_config.trailing_pct)

        # Large PnL - should be damped
        trailing_pct = self.controller._calculate_trailing_percentage(Decimal("0.1"))
        expected = min(
            Decimal("0.05"),  # max_trailing_pct
            Decimal("0.1") * Decimal("0.9")  # net_pnl * damping
        )
        self.assertEqual(trailing_pct, expected)

    def test_no_trigger_below_activation(self):
        """Tests that stop isn't triggered below activation threshold."""
        self.controller.update(
            net_pnl_pct=Decimal("0.015"),  # Below activation (2%)
            current_amount=Decimal("1"),
            on_close_position=self._on_close_position,
            on_partial_close=self._on_partial_close,
        )
        self.assertIsNone(self.controller.pnl_trigger)
        self.assertFalse(self.on_close_called)
        self.assertEqual(self.partial_close_amount, Decimal("0"))

    def test_trigger_on_exact_threshold(self):
        """Tests behavior when PNL hits exactly the trigger price."""
        self.controller.update(net_pnl_pct=Decimal("0.05"), current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        trigger = self.controller.pnl_trigger
        self.controller.update(net_pnl_pct=trigger, current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        self.assertTrue(self.on_close_called)

    def test_find_closest_take_profit(self):
        """Tests finding closest take profit level below current PNL."""
        # Between levels
        self.controller.update(net_pnl_pct=Decimal("0.1"), current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        # Drop to trigger
        self.controller.update(net_pnl_pct=Decimal("0.05"), current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        self.assertEqual(self.partial_close_amount, Decimal("0.5"))  # Should use first level

    def test_sequential_partial_closes(self):
        """Tests behavior with multiple partial closes."""
        # First move up and trigger first level
        self.controller.update(net_pnl_pct=Decimal("0.05"), current_amount=Decimal("1"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        first_trigger = self.controller.pnl_trigger
        self.controller.update(net_pnl_pct=Decimal("0.03"), current_amount=Decimal("0.5"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        # Then move up again to second level
        self.controller.update(net_pnl_pct=Decimal("0.1"), current_amount=Decimal("0.5"),
                               on_close_position=self._on_close_position,
                               on_partial_close=self._on_partial_close)
        second_trigger = self.controller.pnl_trigger
        self.assertGreater(second_trigger, first_trigger)
