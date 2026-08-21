"""An LP position's volume is the swaps that crossed it, not the capital it deposited.

The performance report summed `executor_info.filled_amount_quote` into `volume_traded`.
For every executor that places orders that is the same number — the amount it filled IS
the volume. For an LP executor it is not: `filled_amount_quote` is documented as "the
capital deployed", `initial_base x add_price + initial_quote`. So a position that put up
$100 and traded nothing reported $100 of volume the instant it opened, the report added
it a second time when the executor finished, and `global_pnl_pct` divided PnL by that
figure.

A position does not trade by being funded. What it generates is the swaps that cross its
range, and it holds a direct measurement of those: fees are a fixed fraction of the
volume that paid them.

    volume = fees_earned_in_quote / fee_rate
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor

# The Orca SOL-USDC pool the live LP tests run against: feeRate 400 hundredths of a bip,
# which Gateway reports as feePct 0.04 -- a PERCENT, not a fraction (see GW-2).
ORCA_FEE_PCT = 0.04


def a_config(**overrides) -> LPExecutorConfig:
    fields = dict(
        id="test-volume",
        timestamp=1234567890,
        connector_name="solana-mainnet-beta",
        lp_provider="orca/clmm",
        trading_pair="SOL-USDC",
        pool_address="Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
        lower_price=Decimal("95"),
        upper_price=Decimal("105"),
        base_amount=Decimal("1.0"),
        quote_amount=Decimal("100"),
        side=TradeType.BUY,
    )
    fields.update(overrides)
    return LPExecutorConfig(**fields)


class TestVolumeIsDerivedFromFees(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, fee_pct=ORCA_FEE_PCT, price="100", base_fee="0", quote_fee="0",
                    initial_base="1.0", initial_quote="100") -> LPExecutor:
        executor = LPExecutor(self.strategy, a_config(), update_interval=1.0)
        executor._pool_info = MagicMock(fee_pct=fee_pct) if fee_pct is not None else None
        executor._current_price = Decimal(price)
        executor.lp_position_state.base_fee = Decimal(base_fee)
        executor.lp_position_state.quote_fee = Decimal(quote_fee)
        executor.lp_position_state.initial_base_amount = Decimal(initial_base)
        executor.lp_position_state.initial_quote_amount = Decimal(initial_quote)
        executor.lp_position_state.add_mid_price = Decimal(price)
        return executor

    def test_quote_side_fees_invert_to_the_volume_that_paid_them(self):
        # $1 of fees at 0.04% is $2,500 of swaps across the range.
        executor = self.an_executor(quote_fee="1")

        self.assertEqual(executor.volume_traded_quote, Decimal("2500"))

    def test_base_side_fees_are_valued_before_inverting(self):
        # 0.01 SOL of fees at $100/SOL is $1, so the same $2,500.
        executor = self.an_executor(base_fee="0.01", price="100")

        self.assertEqual(executor.volume_traded_quote, Decimal("2500"))

    def test_both_sides_add_up(self):
        # A range that saw flow in both directions earns on both sides, and one division
        # handles both: (base_fee x price + quote_fee) / rate.
        executor = self.an_executor(base_fee="0.01", quote_fee="1", price="100")

        self.assertEqual(executor.volume_traded_quote, Decimal("5000"))

    def test_a_funded_position_that_has_traded_nothing_reports_no_volume(self):
        """The defect, stated directly: $100 of capital, no fees, no volume."""
        executor = self.an_executor(base_fee="0", quote_fee="0")

        self.assertEqual(executor.volume_traded_quote, Decimal("0"))
        # And the capital it deployed is still reported, under its own name.
        self.assertEqual(executor.filled_amount_quote, Decimal("200"))

    def test_volume_is_not_the_capital_deployed(self):
        """The two must not be the same number -- that sameness WAS the bug."""
        executor = self.an_executor(quote_fee="1")

        self.assertNotEqual(executor.volume_traded_quote, executor.filled_amount_quote)

    def test_a_fee_tier_ten_times_thinner_implies_ten_times_the_volume(self):
        # The same $1 of fees on a 0.004% pool took $25,000 of flow to earn.
        executor = self.an_executor(quote_fee="1", fee_pct=0.004)

        self.assertEqual(executor.volume_traded_quote, Decimal("25000"))

    def test_the_rate_is_read_as_a_percent_not_a_fraction(self):
        """Gateway reports feePct as a PERCENT on every surface (GW-2 made sure of it).

        Reading 0.04 as a fraction would divide by 0.04 instead of 0.0004 and report
        $25 of volume where $2,500 flowed -- 100x low, and plausible enough to go unnoticed.
        """
        executor = self.an_executor(quote_fee="1")

        self.assertEqual(executor.volume_traded_quote, Decimal("2500"))
        self.assertNotEqual(executor.volume_traded_quote, Decimal("25"))


class TestWhenTheRateIsUnknown(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, **kwargs) -> LPExecutor:
        return TestVolumeIsDerivedFromFees.an_executor(self, **kwargs)

    def test_no_pool_info_reports_no_volume_rather_than_a_guess(self):
        """An executor that recovered onto an existing position may never have fetched
        pool info. A missing measurement is not an absence of volume, but inventing a
        fee rate would put a number here that reads as measured and is not.
        """
        executor = self.an_executor(fee_pct=None, quote_fee="1")

        self.assertEqual(executor.volume_traded_quote, Decimal("0"))

    def test_a_zero_fee_rate_reports_no_volume_rather_than_dividing_by_it(self):
        executor = self.an_executor(fee_pct=0, quote_fee="1")

        self.assertEqual(executor.volume_traded_quote, Decimal("0"))

    def test_the_missing_rate_is_said_once_not_every_tick(self):
        executor = self.an_executor(fee_pct=None, quote_fee="1")
        executor.logger = MagicMock()

        for _ in range(5):
            executor.volume_traded_quote

        self.assertEqual(executor.logger.return_value.warning.call_count, 1)


class TestItReachesTheReport(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def test_custom_info_carries_the_volume(self):
        executor = TestVolumeIsDerivedFromFees.an_executor(self, quote_fee="1")

        info = executor.get_custom_info()

        self.assertEqual(info["volume_traded_quote"], 2500.0)
        # Still reported separately, because it is a different fact about the position.
        self.assertEqual(info["base_amount"], 0.0)

    def test_an_order_placing_executor_still_reports_its_filled_amount_as_volume(self):
        """The base class must not change for anything else: for an executor that places
        orders, the amount it filled IS the volume it generated.
        """
        from hummingbot.strategy_v2.executors.executor_base import ExecutorBase

        executor = MagicMock(spec=ExecutorBase)
        executor.filled_amount_quote = Decimal("250")

        self.assertEqual(
            ExecutorBase.volume_traded_quote.fget(executor), Decimal("250")
        )


class TestThePerformanceReport(IsolatedAsyncioWrapperTestCase):
    """The report is where the wrong number was actually visible."""

    def a_report_over(self, executor):
        from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator
        from hummingbot.strategy_v2.models.executors_info import PerformanceReport

        orchestrator = ExecutorOrchestrator.__new__(ExecutorOrchestrator)
        orchestrator.cached_performance = {"main": PerformanceReport()}
        orchestrator.active_executors = {"main": [executor]}
        orchestrator.positions_held = {"main": []}
        orchestrator.strategy = MagicMock()
        return orchestrator.generate_performance_report("main")

    def test_a_live_lp_position_contributes_the_volume_it_generated(self):
        strategy = MagicMock()
        strategy.current_timestamp = 1234567890
        self.strategy = strategy
        executor = TestVolumeIsDerivedFromFees.an_executor(self, quote_fee="1")

        report = self.a_report_over(executor)

        # $2,500 of swaps crossed the range, not the $200 it deposited.
        self.assertEqual(report.volume_traded, Decimal("2500"))

    def test_a_funded_position_that_traded_nothing_contributes_nothing(self):
        """Before: $200 of "volume" the instant it opened, then $200 again on finish."""
        strategy = MagicMock()
        strategy.current_timestamp = 1234567890
        self.strategy = strategy
        executor = TestVolumeIsDerivedFromFees.an_executor(self)

        report = self.a_report_over(executor)

        self.assertEqual(report.volume_traded, Decimal("0"))
        # And with no volume, PnL-over-volume is left alone rather than dividing by capital.
        self.assertEqual(report.global_pnl_pct, Decimal("0"))
