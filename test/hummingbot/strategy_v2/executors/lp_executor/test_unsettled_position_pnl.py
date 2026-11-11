"""A position that has not been polled back has no P&L — not a total loss."""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.lp_executor.data_types import LPExecutorConfig
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor, LPExecutorStates

# The deposit that produced the live reading this test pins down: 5.879999 USDC
# into a ZEC-USDC range at 82.77.
DEPOSIT = Decimal("5.879999")
PRICE = Decimal("82.77")


def a_config(**overrides) -> LPExecutorConfig:
    fields = dict(
        id="test-unsettled",
        timestamp=1234567890,
        connector_name="solana-mainnet-beta",
        lp_provider="orca/clmm",
        trading_pair="ZEC-USDC",
        pool_address="GTHKH8s82ZR8GTSFZ1dUu6wfdxhy59wpMShxzG5zjiPm",
        lower_price=Decimal("78"),
        upper_price=Decimal("86"),
        base_amount=Decimal("0"),
        quote_amount=DEPOSIT,
        side=TradeType.BUY,
    )
    fields.update(overrides)
    return LPExecutorConfig(**fields)


class TestUnsettledPositionPnl(unittest.TestCase):
    def an_executor(self, state, *, base="0", quote="0", initial_quote=str(DEPOSIT),
                    initial_base="0", price=str(PRICE)) -> LPExecutor:
        strategy = MagicMock()
        strategy.current_timestamp = 1234567890
        executor = LPExecutor(strategy, a_config(), update_interval=1.0)
        executor._current_price = Decimal(price)
        executor.lp_position_state.state = state
        executor.lp_position_state.base_amount = Decimal(base)
        executor.lp_position_state.quote_amount = Decimal(quote)
        executor.lp_position_state.initial_base_amount = Decimal(initial_base)
        executor.lp_position_state.initial_quote_amount = Decimal(initial_quote)
        executor.lp_position_state.add_mid_price = Decimal(price)
        executor._get_native_to_quote_rate = lambda: Decimal(price)
        return executor

    def test_a_position_that_has_not_been_polled_back_is_not_a_total_loss(self):
        """The defect, stated directly.

        While the create is in flight the position's holdings are still zero, so
        "current value minus deposit" is the whole deposit. Reported as P&L it is
        a fabrication: nothing was lost, nothing had moved. A downstream drawdown
        guard reads it first and stops the strategy one tick after the deploy.

        Measured live: global_pnl_quote = -5.881992 at t+15s, -0.003962 at t+30s.
        """
        executor = self.an_executor(LPExecutorStates.OPENING)

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_it_is_still_zero_while_an_out_of_range_position_settles(self):
        executor = self.an_executor(LPExecutorStates.SWAPPING, base="0", quote="0")

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_an_unchanged_position_reports_no_pnl(self):
        """Once polled back, the maths is the maths: deposit in, deposit out."""
        executor = self.an_executor(
            LPExecutorStates.IN_RANGE, base="0", quote=str(DEPOSIT),
            initial_quote=str(DEPOSIT),
        )

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))

    def test_a_genuine_loss_is_still_reported(self):
        """The guard must not swallow real losses."""
        executor = self.an_executor(
            LPExecutorStates.IN_RANGE, base="0", quote="5.50", initial_quote=str(DEPOSIT),
        )

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("-0.379999"))

    def test_a_genuine_gain_is_still_reported(self):
        executor = self.an_executor(
            LPExecutorStates.IN_RANGE, base="0", quote="6.10", initial_quote=str(DEPOSIT),
        )

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0.220001"))

    def test_an_executor_that_failed_before_creating_a_position_is_zero(self):
        executor = self.an_executor(LPExecutorStates.FAILED)
        executor.lp_position_state.position_address = ""

        self.assertEqual(executor.get_net_pnl_quote(), Decimal("0"))
