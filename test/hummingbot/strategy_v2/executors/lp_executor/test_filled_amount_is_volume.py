"""An LP position's volume is the swaps that crossed it, not the capital it deposited.

`filled_amount_quote` means the same thing on every executor: the volume it traded. For
one that places orders, the amount filled IS the volume. An LP executor used to return
the capital it deposited instead — `initial_base x add_price + initial_quote` — so a
position that put up $100 and traded nothing reported $100 of volume the instant it
opened, the report added it a second time when the executor finished, and
`global_pnl_pct` divided PnL by that figure.

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
        # `fee_pct="unfetched"` stands for _pool_info still being None — pool info has
        # not been requested yet. Any other value means it HAS been fetched and this is
        # what the pool said, including None or 0.
        executor._pool_info = None if fee_pct == "unfetched" else MagicMock(fee_pct=fee_pct)
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

        self.assertEqual(executor.filled_amount_quote, Decimal("2500"))

    def test_base_side_fees_are_valued_before_inverting(self):
        # 0.01 SOL of fees at $100/SOL is $1, so the same $2,500.
        executor = self.an_executor(base_fee="0.01", price="100")

        self.assertEqual(executor.filled_amount_quote, Decimal("2500"))

    def test_both_sides_add_up(self):
        # A range that saw flow in both directions earns on both sides, and one division
        # handles both: (base_fee x price + quote_fee) / rate.
        executor = self.an_executor(base_fee="0.01", quote_fee="1", price="100")

        self.assertEqual(executor.filled_amount_quote, Decimal("5000"))

    def test_a_funded_position_that_has_traded_nothing_reports_no_volume(self):
        """The defect, stated directly: $200 of capital deposited, no fees, no volume.

        The deposit is deliberately not reported anywhere now. It is not volume, and it
        was only ever exposed here because this property used to return it.
        """
        executor = self.an_executor(base_fee="0", quote_fee="0")

        self.assertEqual(executor.filled_amount_quote, Decimal("0"))

    def test_a_fee_tier_ten_times_thinner_implies_ten_times_the_volume(self):
        # The same $1 of fees on a 0.004% pool took $25,000 of flow to earn.
        executor = self.an_executor(quote_fee="1", fee_pct=0.004)

        self.assertEqual(executor.filled_amount_quote, Decimal("25000"))

    def test_the_rate_is_read_as_a_percent_not_a_fraction(self):
        """Gateway reports feePct as a PERCENT on every surface (GW-2 made sure of it).

        Reading 0.04 as a fraction would divide by 0.04 instead of 0.0004 and report
        $25 of volume where $2,500 flowed -- 100x low, and plausible enough to go unnoticed.
        """
        executor = self.an_executor(quote_fee="1")

        self.assertEqual(executor.filled_amount_quote, Decimal("2500"))
        self.assertNotEqual(executor.filled_amount_quote, Decimal("25"))


class TestWhenTheRateIsUnknown(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self, **kwargs) -> LPExecutor:
        return TestVolumeIsDerivedFromFees.an_executor(self, **kwargs)

    def test_pool_info_not_fetched_yet_reports_no_volume(self):
        """The first read happens before update_pool_info() has ever run."""
        executor = self.an_executor(fee_pct="unfetched", quote_fee="1")

        self.assertEqual(executor.filled_amount_quote, Decimal("0"))

    def test_pool_info_not_fetched_yet_says_NOTHING(self):
        """It must not claim the pool reports no fee rate — it has not been asked.

        This fired one millisecond after an executor was created, on a Meteora pool that
        reports 0.2%:

            04:32:43,552  Creating position: side=RANGE, pool_price=0.256497 ...
            04:32:43,553  WARNING - Pool BetLT47... reports no fee rate ...

        The claim was simply false, and worse, the one-shot flag burned on it: a pool that
        genuinely had no rate would then never be reported at all.
        """
        executor = self.an_executor(fee_pct="unfetched", quote_fee="1")
        executor.logger = MagicMock()

        for _ in range(5):
            executor.filled_amount_quote

        self.assertEqual(executor.logger.return_value.warning.call_count, 0)

    def test_a_pool_that_really_reports_no_rate_is_still_reported(self):
        """Asked, and the answer was no rate. That IS worth saying — once."""
        executor = self.an_executor(fee_pct=0, quote_fee="1")
        executor.logger = MagicMock()

        for _ in range(5):
            self.assertEqual(executor.filled_amount_quote, Decimal("0"))

        self.assertEqual(executor.logger.return_value.warning.call_count, 1)

    def test_a_missing_rate_on_a_fetched_pool_is_reported_too(self):
        executor = self.an_executor(fee_pct=None, quote_fee="1")
        executor.logger = MagicMock()

        executor.filled_amount_quote

        self.assertEqual(executor.logger.return_value.warning.call_count, 1)

    def test_the_warning_quotes_what_the_pool_actually_said(self):
        """So the next reader can tell a 0 from a missing field without re-deriving it."""
        executor = self.an_executor(fee_pct=0, quote_fee="1")
        executor.logger = MagicMock()

        executor.filled_amount_quote

        message = executor.logger.return_value.warning.call_args[0][0]
        self.assertIn("fee rate of 0", message)


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

    def a_report_over(self, executor):
        from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator
        from hummingbot.strategy_v2.models.executors_info import PerformanceReport

        orchestrator = ExecutorOrchestrator.__new__(ExecutorOrchestrator)
        orchestrator.cached_performance = {"main": PerformanceReport()}
        orchestrator.active_executors = {"main": [executor]}
        orchestrator.positions_held = {"main": []}
        orchestrator.strategy = MagicMock()
        return orchestrator.generate_performance_report("main")
