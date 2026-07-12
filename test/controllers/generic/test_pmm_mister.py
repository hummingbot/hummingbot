from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from controllers.generic.pmm_mister import PMMister, PMMisterConfig
from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy


class PMMisterStopPathTest(TestCase):
    def make_controller(self):
        controller = PMMister.__new__(PMMister)
        controller.config = PMMisterConfig(
            id="pmm-stop-test",
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
            total_amount_quote=Decimal("1000"),
            global_sl_enabled=True,
            global_stop_loss=Decimal("0.05"),
        )
        controller._global_close_phase = None
        controller._global_close_side = None
        controller._global_close_retries = 0
        controller.market_data_provider = SimpleNamespace(time=lambda: 1234)
        controller.positions_held = [SimpleNamespace(
            trading_pair="ETH-USDT",
            connector_name="binance_perpetual",
            side=TradeType.BUY,
        )]
        controller.executors_info = []
        return controller

    def test_global_stop_loss_stops_active_executors_before_closing(self):
        controller = self.make_controller()
        controller.processed_data = {
            "current_base_pct": Decimal("0.6"),
            "unrealized_pnl_pct": Decimal("-0.06"),
            "position_amount": Decimal("0.5"),
        }
        controller.executors_info = [SimpleNamespace(
            id="maker-order",
            is_active=True,
            custom_info={"level_id": "buy_0"},
        )]

        actions = controller._check_global_tp_sl()

        self.assertEqual("stopping", controller._global_close_phase)
        self.assertEqual(TradeType.BUY, controller._global_close_side)
        self.assertEqual(["maker-order"], [action.executor_id for action in actions])
        self.assertTrue(actions[0].keep_position)

    def test_protective_close_is_a_market_reduce_action(self):
        controller = self.make_controller()

        action = controller._create_close_action_with_side(TradeType.SELL, Decimal("0.5"))

        self.assertEqual(TradeType.SELL, action.executor_config.side)
        self.assertEqual(PositionAction.CLOSE, action.executor_config.position_action)
        self.assertEqual(ExecutionStrategy.MARKET, action.executor_config.execution_strategy)
        self.assertEqual("global_close", action.executor_config.level_id)
