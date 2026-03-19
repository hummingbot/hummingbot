from decimal import Decimal
from test.hummingbot.strategy_v2.executors.executor_integration_test_base import ExecutorIntegrationTestBase

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.executors.progressive_executor.data_types import (
    LadderedTrailingStop,
    ProgressiveExecutorConfig,
    YieldTripleBarrierConfig,
)
from hummingbot.strategy_v2.executors.progressive_executor.progressive_executor import ProgressiveExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class TestProgressiveExecutorIntegration(ExecutorIntegrationTestBase):

    def create_executor_config(
            self,
            side: TradeType,
            amount: Decimal,
            stop_loss: Decimal = Decimal("0.05"),
            take_profit: Decimal = Decimal("0.1"),
            apr_yield: Decimal = Decimal("0.5"),
            activation_pnl_pct: Decimal = Decimal("0.015"),
            trailing_pct: Decimal = Decimal("0.005"),
            take_profit_table: tuple[tuple[Decimal, Decimal], ...] = (
                (Decimal("0.05"), Decimal("0.5")),
                (Decimal("0.1"), Decimal("1")),
            ),
            time_limit: int = 0,
    ) -> ProgressiveExecutorConfig:
        return ProgressiveExecutorConfig(
            type="progressive_executor",
            timestamp=self.start_timestamp,
            connector_name="mock_paper_exchange",
            trading_pair=self.trading_pair,
            side=side,
            amount=amount,
            entry_price=self.initial_price,
            triple_barrier_config=YieldTripleBarrierConfig(
                stop_loss=stop_loss,
                take_profit=take_profit,
                apr_yield=apr_yield,
                time_limit=time_limit,
                stop_loss_order_type=OrderType.MARKET,
                time_limit_order_type=OrderType.MARKET,
                trailing_stop=LadderedTrailingStop(
                    activation_pnl_pct=activation_pnl_pct,
                    trailing_pct=trailing_pct,
                    take_profit_table=take_profit_table,
                ),
            ),
        )

    async def test_long_position_stop_loss(self):
        amount = Decimal("1")
        stop_loss = Decimal("0.05")
        stop_loss_price = self.initial_price * (Decimal("1") - stop_loss)

        config = self.create_executor_config(
            side=TradeType.BUY,
            amount=amount,
            stop_loss=stop_loss,
        )

        self.executor = ProgressiveExecutor(self.strategy, config)
        self.set_loggers([self.executor.logger()])
        self.executor.start()

        await self.run_executor_until_ready()
        self.assertEqual(RunnableStatus.RUNNING, self.executor.status)
        self.assertIsNotNone(self.executor.open_order, "Order should have been placed")
        self.assertGreater(self.executor.open_filled_amount, Decimal("0"), "Order should have been filled")

        self.simulate_side_price_change(stop_loss_price * Decimal("0.9"),
                                        TradeType.BUY)  # Simulate price drop below stop loss
        self.advance_clock(5)
        await self.executor.control_task()
        self.advance_clock(5)

        self.assertEqual(CloseType.STOP_LOSS, self.executor.close_type)
        self.assertEqual(RunnableStatus.SHUTTING_DOWN, self.executor.status)

    async def test_long_position_trailing_stop(self):
        """
        Test that the ProgressiveExecutor can place a trailing stop order for a short position

        Expected behavior:
        - The executor should place a trailing stop order at 1.5% below the initial price
        - The executor should close the position when the price hits the trailing stop price
        """
        amount = Decimal("1")
        trailing_pct = Decimal("0.015")
        activation_pnl_pct = Decimal("0.02")

        config = self.create_executor_config(
            side=TradeType.BUY,
            amount=amount,
            trailing_pct=trailing_pct,
            activation_pnl_pct=activation_pnl_pct,
        )
        self.executor = ProgressiveExecutor(self.strategy, config)
        self.executor.start()

        await self.run_executor_until_ready()
        self.assertEqual(RunnableStatus.RUNNING, self.executor.status)
        self.assertIsNone(self.executor.trailing_stop_manager.pnl_trigger)
        # Reset the order book so the close_price is aligned with the entry_price (normally it would be slightly off)
        self.simulate_side_price_change(self.executor.entry_price, TradeType.SELL)
        self.assertEqual(self.executor.close_price, self.executor.entry_price)

        # Trigger the trailing stop with the activation PnL
        activation_price = self.executor.entry_price * (Decimal("1") + activation_pnl_pct)
        self.simulate_side_price_change(activation_price, TradeType.SELL)
        self.assertEqual(activation_price, self.executor.close_price)
        await self.executor.control_task()
        self.advance_clock()
        self.assertIsNotNone(self.executor.trailing_stop_manager.pnl_trigger, "Trailing stop trigger price should have been set")
        # The trailing stop trigger PnL is affected by the damping_factor and the gradual increase of risk tolerance
        self.assertGreaterEqual(activation_pnl_pct - trailing_pct, self.executor.trailing_stop_manager.pnl_trigger)

        # Simulate a price increase by 5% after the activation PnL
        pnl = Decimal("0.05")
        peak_price = activation_price * (Decimal("1") + pnl)
        self.simulate_price_change(peak_price)
        await self.executor.control_task()
        self.advance_clock(5)
        self.assertIsNotNone(self.executor.trailing_stop_manager.pnl_trigger)
        self.assertGreaterEqual(pnl - trailing_pct, self.executor.trailing_stop_manager.pnl_trigger)

        # Simulate a price drop that doesn't trigger the trailing stop
        almost_trigger_price = peak_price * (Decimal("1") - trailing_pct / 2)
        self.simulate_price_change(almost_trigger_price)
        await self.executor.control_task()
        self.advance_clock()
        self.assertIsNotNone(self.executor.trailing_stop_manager.pnl_trigger)
        self.assertGreaterEqual(pnl - trailing_pct, self.executor.trailing_stop_manager.pnl_trigger)

        # Simulate a price drop that triggers the trailing stop - with the damping factor, the trigger price is lower
        trigger_price = peak_price * (Decimal("1") - pnl)
        self.simulate_price_change(trigger_price)
        await self.executor.control_task()
        self.advance_clock(5)  # Allow time for order placement and processing

        self.assertEqual(CloseType.TRAILING_STOP, self.executor.close_type)
        self.assertEqual(RunnableStatus.SHUTTING_DOWN, self.executor.status)

    async def test_position_time_limit(self):
        config = self.create_executor_config(
            side=TradeType.BUY,
            amount=Decimal("1"),
            time_limit=5,
        )
        self.executor = ProgressiveExecutor(self.strategy, config)
        self.executor.start()

        await self.run_executor_until_ready()
        self.assertEqual(RunnableStatus.RUNNING, self.executor.status)

        self.advance_clock(6)
        # The position should be extended for a positive PnL
        self.simulate_price_change(self.executor.entry_price * Decimal("1.02"))
        await self.executor.control_task()
        self.advance_clock()
        self.assertEqual(None, self.executor.close_type)

        self.advance_clock(6)
        # The position should be closed after the time limit is reached, simulate negative PnL
        self.simulate_price_change(self.executor.entry_price * Decimal("0.9"))
        await self.executor.control_task()
        self.advance_clock()

        self.assertEqual(CloseType.TIME_LIMIT, self.executor.close_type)
        self.assertEqual(RunnableStatus.SHUTTING_DOWN, self.executor.status)
