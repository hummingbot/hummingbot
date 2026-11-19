from decimal import Decimal
from unittest import TestCase

from pydantic import ValidationError

from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import (
    LPAmmExecutorConfig,
    LPAmmExecutorState,
    LPAmmExecutorStates,
)
from hummingbot.strategy_v2.models.executors import TrackedOrder


class TestLPAmmExecutorStates(TestCase):
    def test_states_enum_values(self):
        self.assertEqual(LPAmmExecutorStates.NOT_ACTIVE.value, "NOT_ACTIVE")
        self.assertEqual(LPAmmExecutorStates.OPENING.value, "OPENING")
        self.assertEqual(LPAmmExecutorStates.ACTIVE.value, "ACTIVE")
        self.assertEqual(LPAmmExecutorStates.CLOSING.value, "CLOSING")
        self.assertEqual(LPAmmExecutorStates.COMPLETE.value, "COMPLETE")
        self.assertEqual(LPAmmExecutorStates.FAILED.value, "FAILED")
        # No IN_RANGE/OUT_OF_RANGE: a full-range position has no price range.
        self.assertFalse(hasattr(LPAmmExecutorStates, "IN_RANGE"))
        self.assertFalse(hasattr(LPAmmExecutorStates, "OUT_OF_RANGE"))


class TestLPAmmExecutorConfig(TestCase):
    def get_kwargs(self, **overrides) -> dict:
        kwargs = dict(
            id="test-amm-1",
            timestamp=1234567890,
            connector_name="solana-mainnet-beta",
            lp_provider="meteora/amm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            base_amount=Decimal("1.0"),
            quote_amount=Decimal("100"),
        )
        kwargs.update(overrides)
        return kwargs

    def test_config_creation_minimal(self):
        config = LPAmmExecutorConfig(**self.get_kwargs())
        self.assertEqual(config.type, "lp_amm_executor")
        self.assertEqual(config.connector_name, "solana-mainnet-beta")
        self.assertEqual(config.lp_provider, "meteora/amm")
        self.assertEqual(config.pool_address, "pool123")
        self.assertEqual(config.base_amount, Decimal("1.0"))
        self.assertEqual(config.quote_amount, Decimal("100"))
        self.assertIsNone(config.min_fee_apr_pct)
        self.assertIsNone(config.max_duration_seconds)
        self.assertEqual(config.position_refresh_interval, 1.0)
        self.assertEqual(config.min_fee_apr_window_seconds, 3600.0)
        self.assertFalse(config.keep_position)
        # LPAmmExecutorConfig has no range: these fields don't exist on it at all.
        self.assertFalse(hasattr(config, "lower_price"))
        self.assertFalse(hasattr(config, "upper_price"))

    def test_config_with_exit_triggers(self):
        config = LPAmmExecutorConfig(**self.get_kwargs(
            min_fee_apr_pct=Decimal("5"),
            max_duration_seconds=86400.0,
        ))
        self.assertEqual(config.min_fee_apr_pct, Decimal("5"))
        self.assertEqual(config.max_duration_seconds, 86400.0)

    def test_both_amounts_zero_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(base_amount=Decimal("0"), quote_amount=Decimal("0")))

    def test_bad_provider_format_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(lp_provider="meteora"))

    def test_bad_trading_pair_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(trading_pair="SOLUSDC"))

    def test_empty_pool_address_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(pool_address=""))

    def test_slippage_above_max_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(slippage_pct=Decimal("10"), max_slippage_pct=Decimal("5")))

    def test_slippage_multiplier_must_exceed_one(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(slippage_multiplier=Decimal("1")))

    def test_non_positive_min_fee_apr_pct_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(min_fee_apr_pct=Decimal("0")))

    def test_non_positive_max_duration_rejected(self):
        with self.assertRaises(ValidationError):
            LPAmmExecutorConfig(**self.get_kwargs(max_duration_seconds=0.0))


class TestLPAmmExecutorStateMath(TestCase):
    """
    Pure-function checks for the IL / fee-APR model.

    Fixture: a balanced deposit of base=1, quote=100 at price=100 (k=100).
    - At an unchanged price, the no-fee curve equals the initial deposit value,
      so IL is 0 regardless of how much the reserves grew from fees.
    - At a point exactly ON the no-fee curve for a new price, fees are 0 and
      IL is the textbook constant-product IL for that price ratio.
    """

    def test_invariant_k(self):
        state = LPAmmExecutorState(initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"))
        self.assertEqual(state.invariant_k(), Decimal("100"))

    def test_value_no_fee_quote_matches_initial_deposit_at_add_price(self):
        state = LPAmmExecutorState(initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"))
        # 2 * sqrt(100 * 100) = 200 == initial deposit value (1*100 + 100)
        self.assertEqual(state.value_no_fee_quote(Decimal("100")), Decimal("200"))

    def test_fees_earned_when_price_unchanged(self):
        state = LPAmmExecutorState(
            initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"),
            base_amount=Decimal("1.01"), quote_amount=Decimal("101"),
        )
        # current_value = 1.01*100 + 101 = 202; no-fee curve at price 100 = 200
        self.assertEqual(state.current_value_quote(Decimal("100")), Decimal("202"))
        self.assertEqual(state.fees_earned_quote(Decimal("100")), Decimal("2"))
        # Price never moved, so holding and the no-fee curve agree: no IL.
        self.assertEqual(state.impermanent_loss_quote(Decimal("100")), Decimal("0"))

    def test_impermanent_loss_on_the_no_fee_curve(self):
        # Reserves rebalanced to exactly the no-fee curve at price=400 (4x):
        # base = sqrt(k/p) = sqrt(100/400) = 0.5, quote = sqrt(k*p) = sqrt(40000) = 200.
        state = LPAmmExecutorState(
            initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"),
            base_amount=Decimal("0.5"), quote_amount=Decimal("200"),
        )
        self.assertEqual(state.current_value_quote(Decimal("400")), Decimal("400"))
        self.assertEqual(state.value_no_fee_quote(Decimal("400")), Decimal("400"))
        self.assertEqual(state.fees_earned_quote(Decimal("400")), Decimal("0"))
        # held_value = 1*400 + 100 = 500; IL = 500 - 400 = 100
        self.assertEqual(state.held_value_quote(Decimal("400")), Decimal("500"))
        self.assertEqual(state.impermanent_loss_quote(Decimal("400")), Decimal("100"))

    def test_fee_apr_pct_one_percent_over_one_year(self):
        state = LPAmmExecutorState(
            initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"),
            base_amount=Decimal("1.01"), quote_amount=Decimal("101"),
            add_price=Decimal("100"), add_timestamp=0.0,
        )
        # fees_earned=2 on an initial deposit of 200, over exactly one year -> 1%
        one_year_later = 365 * 86400.0
        fee_apr = state.fee_apr_pct(Decimal("100"), one_year_later)
        self.assertAlmostEqual(float(fee_apr), 1.0, places=6)

    def test_fee_apr_pct_none_without_add_timestamp(self):
        state = LPAmmExecutorState(initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"))
        self.assertIsNone(state.fee_apr_pct(Decimal("100"), 1000.0))

    def test_fee_apr_pct_none_at_zero_elapsed(self):
        state = LPAmmExecutorState(
            initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"),
            add_price=Decimal("100"), add_timestamp=1000.0,
        )
        self.assertIsNone(state.fee_apr_pct(Decimal("100"), 1000.0))

    def test_fee_apr_pct_none_without_add_price(self):
        state = LPAmmExecutorState(
            initial_base_amount=Decimal("1"), initial_quote_amount=Decimal("100"),
            add_timestamp=0.0,
        )
        self.assertIsNone(state.fee_apr_pct(Decimal("100"), 1000.0))


class TestLPAmmExecutorStateTransitions(TestCase):
    def test_initial_state_is_not_active(self):
        state = LPAmmExecutorState()
        self.assertEqual(state.state, LPAmmExecutorStates.NOT_ACTIVE)

    def test_opening_while_open_order_active(self):
        state = LPAmmExecutorState(active_open_order=TrackedOrder(order_id="o1"))
        state.update_state()
        self.assertEqual(state.state, LPAmmExecutorStates.OPENING)

    def test_opening_preserved_until_position_opened(self):
        state = LPAmmExecutorState(state=LPAmmExecutorStates.OPENING)
        state.update_state()
        self.assertEqual(state.state, LPAmmExecutorStates.OPENING)

    def test_active_once_position_opened(self):
        state = LPAmmExecutorState(state=LPAmmExecutorStates.OPENING, position_opened=True)
        state.update_state()
        self.assertEqual(state.state, LPAmmExecutorStates.ACTIVE)

    def test_closing_while_close_order_active(self):
        state = LPAmmExecutorState(
            state=LPAmmExecutorStates.ACTIVE, position_opened=True,
            active_close_order=TrackedOrder(order_id="o2"),
        )
        state.update_state()
        self.assertEqual(state.state, LPAmmExecutorStates.CLOSING)

    def test_terminal_states_preserved(self):
        for terminal in (LPAmmExecutorStates.COMPLETE, LPAmmExecutorStates.CLOSING, LPAmmExecutorStates.FAILED):
            state = LPAmmExecutorState(state=terminal, position_opened=True)
            state.update_state()
            self.assertEqual(state.state, terminal)
