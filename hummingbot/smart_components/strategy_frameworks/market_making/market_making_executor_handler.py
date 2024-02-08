import logging
from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorStatus
from hummingbot.smart_components.models.executors import CloseType
from hummingbot.smart_components.strategy_frameworks.executor_handler_base import ExecutorHandlerBase
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_controller_base import (
    MarketMakingControllerBase,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingExecutorHandler(ExecutorHandlerBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, controller: MarketMakingControllerBase,
                 update_interval: float = 1.0, executors_update_interval: float = 1.0):
        super().__init__(strategy, controller, update_interval, executors_update_interval)
        self.controller = controller
        self.position_executors = {level.level_id: None for level in self.controller.config.order_levels}
        self.global_trailing_stop_config = self.controller.config.global_trailing_stop_config
        self._trailing_stop_pnl_by_side: Dict[TradeType, Optional[Decimal]] = {TradeType.BUY: None, TradeType.SELL: None}

    def on_stop(self):
        if self.controller.is_perpetual:
            self.close_open_positions(connector_name=self.controller.config.exchange, trading_pair=self.controller.config.trading_pair)
        super().on_stop()

    def on_start(self):
        super().on_start()
        if self.controller.is_perpetual:
            self.set_leverage_and_position_mode()

    def set_leverage_and_position_mode(self):
        connector = self.strategy.connectors[self.controller.config.exchange]
        connector.set_position_mode(self.controller.config.position_mode)
        connector.set_leverage(trading_pair=self.controller.config.trading_pair, leverage=self.controller.config.leverage)

    @staticmethod
    def empty_metrics_dict():
        return {"amount": Decimal("0"), "net_pnl_quote": Decimal("0"), "executors": []}

    async def control_task(self):
        if self.controller.all_candles_ready:
            current_metrics = {
                TradeType.BUY: self.empty_metrics_dict(),
                TradeType.SELL: self.empty_metrics_dict()}
            for order_level in self.controller.config.order_levels:
                current_executor = self.position_executors[order_level.level_id]
                if current_executor:
                    closed_and_not_in_cooldown = current_executor.is_closed and not self.controller.cooldown_condition(
                        current_executor, order_level) or current_executor.close_type == CloseType.EXPIRED
                    active_and_early_stop_condition = current_executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION and self.controller.early_stop_condition(
                        current_executor, order_level)
                    order_placed_and_refresh_condition = current_executor.executor_status == PositionExecutorStatus.NOT_STARTED and self.controller.refresh_order_condition(
                        current_executor, order_level)
                    if closed_and_not_in_cooldown:
                        self.store_position_executor(order_level.level_id)
                    elif active_and_early_stop_condition or order_placed_and_refresh_condition:
                        current_executor.early_stop()
                    elif current_executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
                        current_metrics[current_executor.side]["amount"] += current_executor.filled_amount * current_executor.entry_price
                        current_metrics[current_executor.side]["net_pnl_quote"] += current_executor.net_pnl_quote
                        current_metrics[current_executor.side]["executors"].append(current_executor)
                else:
                    position_config = self.controller.get_position_config(order_level)
                    if position_config:
                        self.create_position_executor(position_config, order_level.level_id)
            if self.global_trailing_stop_config:
                for side, global_trailing_stop_conf in self.global_trailing_stop_config.items():
                    if current_metrics[side]["amount"] > 0:
                        current_pnl_pct = current_metrics[side]["net_pnl_quote"] / current_metrics[side]["amount"]
                        trailing_stop_pnl = self._trailing_stop_pnl_by_side[side]
                        if not trailing_stop_pnl and current_pnl_pct > global_trailing_stop_conf.activation_price:
                            self._trailing_stop_pnl_by_side[side] = current_pnl_pct - global_trailing_stop_conf.trailing_delta
                            self.logger().info("Global Trailing Stop Activated!")
                        if trailing_stop_pnl:
                            if current_pnl_pct < trailing_stop_pnl:
                                self.logger().info("Global Trailing Stop Triggered!")
                                for executor in current_metrics[side]["executors"]:
                                    executor.early_stop()
                                self._trailing_stop_pnl_by_side[side] = None
                            elif current_pnl_pct - global_trailing_stop_conf.trailing_delta > trailing_stop_pnl:
                                self._trailing_stop_pnl_by_side[side] = current_pnl_pct - global_trailing_stop_conf.trailing_delta
