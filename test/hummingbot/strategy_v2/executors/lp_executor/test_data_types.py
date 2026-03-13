from decimal import Decimal
from unittest import TestCase

from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorState, LPExecutorStates
from hummingbot.strategy_v2.models.executors import TrackedOrder


class TestLPExecutorStates(TestCase):
    """Test LPExecutorStates enum"""

    def test_states_enum_values(self):
        """Verify all state enum values"""
        self.assertEqual(LPExecutorStates.NOT_ACTIVE.value, "NOT_ACTIVE")
        self.assertEqual(LPExecutorStates.OPENING.value, "OPENING")
        self.assertEqual(LPExecutorStates.IN_RANGE.value, "IN_RANGE")
        self.assertEqual(LPExecutorStates.OUT_OF_RANGE.value, "OUT_OF_RANGE")
        self.assertEqual(LPExecutorStates.CLOSING.value, "CLOSING")
        self.assertEqual(LPExecutorStates.COMPLETE.value, "COMPLETE")

    def test_states_enum_names(self):
        """Verify all state enum names"""
        self.assertEqual(LPExecutorStates.NOT_ACTIVE.name, "NOT_ACTIVE")
        self.assertEqual(LPExecutorStates.OPENING.name, "OPENING")
        self.assertEqual(LPExecutorStates.IN_RANGE.name, "IN_RANGE")
        self.assertEqual(LPExecutorStates.OUT_OF_RANGE.name, "OUT_OF_RANGE")
        self.assertEqual(LPExecutorStates.CLOSING.name, "CLOSING")
        self.assertEqual(LPExecutorStates.COMPLETE.name, "COMPLETE")


class TestLPExecutorConfig(TestCase):
    """Test LPExecutorConfig"""

    def test_config_creation_minimal(self):
        """Test creating config with minimal required fields"""
        config = LPExecutorConfig(
            id="test-1",
            timestamp=1234567890,
            connector_name="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            lower_price=Decimal("100"),
            upper_price=Decimal("110"),
        )
        self.assertEqual(config.type, "lp_executor")
        self.assertEqual(config.connector_name, "meteora/clmm")
        self.assertEqual(config.trading_pair, "SOL-USDC")
        self.assertEqual(config.pool_address, "pool123")
        self.assertEqual(config.lower_price, Decimal("100"))
        self.assertEqual(config.upper_price, Decimal("110"))
        self.assertEqual(config.base_amount, Decimal("0"))
        self.assertEqual(config.quote_amount, Decimal("0"))
        self.assertEqual(config.side, 0)
        self.assertIsNone(config.auto_close_above_range_seconds)
        self.assertIsNone(config.auto_close_below_range_seconds)
        self.assertIsNone(config.extra_params)
        self.assertFalse(config.keep_position)

    def test_config_creation_full(self):
        """Test creating config with all fields"""
        config = LPExecutorConfig(
            id="test-2",
            timestamp=1234567890,
            connector_name="meteora/clmm",
            trading_pair="SOL-USDC",
            pool_address="pool456",
            lower_price=Decimal("90"),
            upper_price=Decimal("100"),
            base_amount=Decimal("1.5"),
            quote_amount=Decimal("150"),
            side=1,
            auto_close_above_range_seconds=300,
            auto_close_below_range_seconds=600,
            extra_params={"strategyType": 0},
            keep_position=True,
        )
        self.assertEqual(config.base_amount, Decimal("1.5"))
        self.assertEqual(config.quote_amount, Decimal("150"))
        self.assertEqual(config.side, 1)
        self.assertEqual(config.auto_close_above_range_seconds, 300)
        self.assertEqual(config.auto_close_below_range_seconds, 600)
        self.assertEqual(config.extra_params, {"strategyType": 0})
        self.assertTrue(config.keep_position)

    def test_config_side_values(self):
        """Test different side values: 0=BOTH, 1=BUY, 2=SELL"""
        for side in [0, 1, 2]:
            config = LPExecutorConfig(
                id=f"test-side-{side}",
                timestamp=1234567890,
                connector_name="meteora/clmm",
                trading_pair="SOL-USDC",
                pool_address="pool",
                lower_price=Decimal("100"),
                upper_price=Decimal("110"),
                side=side,
            )
            self.assertEqual(config.side, side)


class TestLPExecutorState(TestCase):
    """Test LPExecutorState"""

    def test_state_creation_defaults(self):
        """Test creating state with defaults"""
        state = LPExecutorState()
        self.assertIsNone(state.position_address)
        self.assertEqual(state.lower_price, Decimal("0"))
        self.assertEqual(state.upper_price, Decimal("0"))
        self.assertEqual(state.base_amount, Decimal("0"))
        self.assertEqual(state.quote_amount, Decimal("0"))
        self.assertEqual(state.base_fee, Decimal("0"))
        self.assertEqual(state.quote_fee, Decimal("0"))
        self.assertEqual(state.position_rent, Decimal("0"))
        self.assertEqual(state.position_rent_refunded, Decimal("0"))
        self.assertIsNone(state.active_open_order)
        self.assertIsNone(state.active_close_order)
        self.assertEqual(state.state, LPExecutorStates.NOT_ACTIVE)
        self.assertIsNone(state._out_of_range_since)

    def test_state_with_values(self):
        """Test state with custom values"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
            base_amount=Decimal("2.0"),
            quote_amount=Decimal("200"),
            base_fee=Decimal("0.01"),
            quote_fee=Decimal("1.0"),
            position_rent=Decimal("0.002"),
            state=LPExecutorStates.IN_RANGE,
        )
        self.assertEqual(state.position_address, "pos123")
        self.assertEqual(state.lower_price, Decimal("95"))
        self.assertEqual(state.upper_price, Decimal("105"))
        self.assertEqual(state.base_amount, Decimal("2.0"))
        self.assertEqual(state.quote_amount, Decimal("200"))
        self.assertEqual(state.base_fee, Decimal("0.01"))
        self.assertEqual(state.quote_fee, Decimal("1.0"))
        self.assertEqual(state.position_rent, Decimal("0.002"))
        self.assertEqual(state.state, LPExecutorStates.IN_RANGE)

    def test_get_out_of_range_seconds_none(self):
        """Test get_out_of_range_seconds returns None when in range"""
        state = LPExecutorState()
        self.assertIsNone(state.get_out_of_range_seconds(1000.0))

    def test_get_out_of_range_seconds_with_value(self):
        """Test get_out_of_range_seconds returns correct duration"""
        state = LPExecutorState()
        state._out_of_range_since = 1000.0
        self.assertEqual(state.get_out_of_range_seconds(1030.0), 30)
        self.assertEqual(state.get_out_of_range_seconds(1060.5), 60)

    def test_update_state_complete_preserved(self):
        """Test that COMPLETE state is preserved"""
        state = LPExecutorState(state=LPExecutorStates.COMPLETE)
        state.update_state(Decimal("100"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.COMPLETE)

    def test_update_state_closing_preserved(self):
        """Test that CLOSING state is preserved"""
        state = LPExecutorState(state=LPExecutorStates.CLOSING)
        state.update_state(Decimal("100"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.CLOSING)

    def test_update_state_with_close_order(self):
        """Test state becomes CLOSING when close order active"""
        state = LPExecutorState()
        state.active_close_order = TrackedOrder(order_id="close-1")
        state.update_state(Decimal("100"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.CLOSING)

    def test_update_state_with_open_order_no_position(self):
        """Test state becomes OPENING when open order active but no position"""
        state = LPExecutorState()
        state.active_open_order = TrackedOrder(order_id="open-1")
        state.update_state(Decimal("100"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.OPENING)

    def test_update_state_in_range(self):
        """Test state becomes IN_RANGE when price is within bounds"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
        )
        state.update_state(Decimal("100"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.IN_RANGE)

    def test_update_state_out_of_range_below(self):
        """Test state becomes OUT_OF_RANGE when price below lower bound"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
        )
        state.update_state(Decimal("90"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.OUT_OF_RANGE)
        self.assertEqual(state._out_of_range_since, 1000.0)

    def test_update_state_out_of_range_above(self):
        """Test state becomes OUT_OF_RANGE when price above upper bound"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
        )
        state.update_state(Decimal("110"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.OUT_OF_RANGE)

    def test_update_state_resets_out_of_range_timer(self):
        """Test that returning to in_range resets the timer"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
        )
        # Go out of range
        state.update_state(Decimal("110"), 1000.0)
        self.assertEqual(state._out_of_range_since, 1000.0)

        # Come back in range
        state.update_state(Decimal("100"), 1030.0)
        self.assertEqual(state.state, LPExecutorStates.IN_RANGE)
        self.assertIsNone(state._out_of_range_since)

    def test_update_state_not_active_without_position(self):
        """Test state is NOT_ACTIVE when no position address"""
        state = LPExecutorState()
        state.update_state(Decimal("100"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.NOT_ACTIVE)

    def test_update_state_at_boundary_lower(self):
        """Test price at lower bound is considered in range"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
        )
        state.update_state(Decimal("95"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.IN_RANGE)

    def test_update_state_at_boundary_upper(self):
        """Test price at upper bound is considered in range"""
        state = LPExecutorState(
            position_address="pos123",
            lower_price=Decimal("95"),
            upper_price=Decimal("105"),
        )
        state.update_state(Decimal("105"), 1000.0)
        self.assertEqual(state.state, LPExecutorStates.IN_RANGE)
