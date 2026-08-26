"""Slippage widens across retries, and only when slippage is what failed.

Before this, no executor had a slippage setting at all: the request omitted slippagePct,
so every attempt used the connector's configured value and every retry repeated the same
request. A close that failed on slippage failed ten identical times, paying gas on any
attempt that reached the chain, and the operator's only lever was a per-connector YAML
value applying to every operation that connector performed.
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_error import GatewayError
from hummingbot.strategy_v2.executors.gateway_utils import is_slippage_failure, next_slippage_pct
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig, LPExecutorStates
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor


def a_config(**overrides) -> LPExecutorConfig:
    fields = dict(
        id="test-slippage",
        timestamp=1234567890,
        connector_name="solana-mainnet-beta",
        lp_provider="orca/clmm",
        trading_pair="SOL-USDC",
        pool_address="pool123",
        lower_price=Decimal("95"),
        upper_price=Decimal("105"),
        base_amount=Decimal("1.0"),
        quote_amount=Decimal("100"),
        side=TradeType.BUY,
    )
    fields.update(overrides)
    return LPExecutorConfig(**fields)


class TestTheRamp(IsolatedAsyncioWrapperTestCase):
    def test_the_default_ramp_reaches_the_ceiling_in_three_widenings(self):
        config = a_config()
        rungs = [config.slippage_pct]
        while True:
            nxt = next_slippage_pct(rungs[-1], config.slippage_multiplier, config.max_slippage_pct)
            if nxt is None:
                break
            rungs.append(nxt)

        self.assertEqual(rungs, [Decimal("0.05"), Decimal("0.25"), Decimal("1.25"), Decimal("5")])

    def test_the_ceiling_is_never_exceeded(self):
        # 1.25 x 5 is 6.25, which is past the cap.
        self.assertEqual(next_slippage_pct(Decimal("1.25"), Decimal("5"), Decimal("5")), Decimal("5"))

    def test_at_the_ceiling_there_is_no_next_rung(self):
        # An answer, not a failure to compute one: the market has moved past what the
        # operator agreed to pay.
        self.assertIsNone(next_slippage_pct(Decimal("5"), Decimal("5"), Decimal("5")))


class TestSlippageAttribution(IsolatedAsyncioWrapperTestCase):
    def test_reads_gateways_code(self):
        self.assertTrue(is_slippage_failure(GatewayError("too tight", status=400, code="SLIPPAGE_EXCEEDED")))

    def test_reads_the_code_out_of_a_re_raised_message(self):
        # The connector's retry wrapper re-raises some failures as a plain Exception,
        # and the rendered GatewayError string still carries the code.
        self.assertTrue(is_slippage_failure(Exception("Gateway error: ... [code: SLIPPAGE_EXCEEDED]")))

    def test_ignores_every_other_failure(self):
        for other in (
            GatewayError("no funds", status=400, code="INSUFFICIENT_BALANCE"),
            GatewayError("bad tick", status=400, code="SIMULATION_FAILED"),
            ConnectionError("gateway restarting"),
        ):
            self.assertFalse(is_slippage_failure(other), other)


class TestTheExecutorWidens(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, config: LPExecutorConfig = None) -> LPExecutor:
        return LPExecutor(self.strategy, config or a_config(), update_interval=1.0)

    def test_a_close_that_fails_on_slippage_retries_wider(self):
        executor = self.an_executor()

        executor._handle_close_failure(GatewayError("too tight", status=400, code="SLIPPAGE_EXCEEDED"))

        self.assertEqual(executor._slippage_pct, Decimal("0.25"))

    def test_a_close_that_fails_on_anything_else_retries_at_the_same_tolerance(self):
        executor = self.an_executor()

        executor._handle_close_failure(ConnectionError("gateway restarting"))

        # Loosening a tolerance that was never the problem spends money to fix the
        # wrong thing.
        self.assertEqual(executor._slippage_pct, Decimal("0.05"))

    def test_an_exit_at_the_ceiling_keeps_trying(self):
        executor = self.an_executor()
        executor._slippage_pct = Decimal("5")

        executor._handle_close_failure(GatewayError("too tight", status=400, code="SLIPPAGE_EXCEEDED"))

        # Still CLOSING, still at the cap: the position is real and has to come out.
        self.assertEqual(executor._slippage_pct, Decimal("5"))

    def test_an_open_that_fails_on_slippage_is_retried_rather_than_abandoned(self):
        executor = self.an_executor()

        executor._handle_create_failure(GatewayError("too tight", status=400, code="SLIPPAGE_EXCEEDED"))

        # Safe because SLIPPAGE_EXCEEDED means the transaction did not take effect —
        # rejected at simulation, or landed and reverted. There is no first deposit for
        # a retry to land on top of, which is the risk that makes other open failures
        # terminal.
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.OPENING)
        self.assertEqual(executor._slippage_pct, Decimal("0.25"))
        self.assertEqual(executor._current_retries, 1)

    def test_an_open_that_fails_on_anything_else_is_still_terminal(self):
        executor = self.an_executor()

        executor._handle_create_failure(ValueError("no position address in response"))

        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    def test_an_open_at_the_ceiling_stops_rather_than_paying_more(self):
        executor = self.an_executor()
        executor._slippage_pct = Decimal("5")

        executor._handle_create_failure(GatewayError("too tight", status=400, code="SLIPPAGE_EXCEEDED"))

        # Nothing is stranded by giving up on an entry, so the ceiling ends it.
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.FAILED)

    def test_an_open_whose_position_already_landed_is_never_retried(self):
        executor = self.an_executor()
        executor.lp_position_state.position_address = "pos123"

        executor._handle_create_failure(GatewayError("too tight", status=400, code="SLIPPAGE_EXCEEDED"))

        # A retry here would deposit a second position on top of the first.
        self.assertEqual(executor.lp_position_state.state, LPExecutorStates.CLOSING)

    def test_the_next_phase_starts_tight_again(self):
        executor = self.an_executor()
        executor._slippage_pct = Decimal("1.25")

        executor._reset_slippage()

        self.assertEqual(executor._slippage_pct, Decimal("0.05"))


class TestConfigValidation(IsolatedAsyncioWrapperTestCase):
    def test_a_start_above_the_ceiling_is_rejected(self):
        with self.assertRaises(ValueError):
            a_config(slippage_pct=Decimal("10"), max_slippage_pct=Decimal("5"))

    def test_a_multiplier_that_never_widens_is_rejected(self):
        # max_slippage_pct would be a promise the ramp could not keep.
        with self.assertRaises(ValueError):
            a_config(slippage_multiplier=Decimal("1"))

    def test_zero_slippage_is_rejected(self):
        with self.assertRaises(ValueError):
            a_config(slippage_pct=Decimal("0"))
