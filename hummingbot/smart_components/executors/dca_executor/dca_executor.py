import logging
from decimal import Decimal
from typing import List, Optional

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.executors.dca_executor.data_types import DCAConfig
from hummingbot.smart_components.executors.position_executor.data_types import CloseType, PositionConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DCAExecutor(SmartComponentBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, dca_config: DCAConfig, update_interval: float = 1.0):
        if dca_config.time_limit_order_type != OrderType.MARKET or dca_config.stop_loss_order_type != OrderType.MARKET:
            error = "Only market orders are supported for time_limit and stop_loss"
            self.logger().error(error)
            raise ValueError(error)
        self._dca_config: DCAConfig = dca_config
        self.close_type = None
        self.close_timestamp = None

        # executors tracking
        self._active_executors: List[PositionExecutor] = []
        self._trailing_stop_activated = False
        self._trailing_stop_pnl = None
        self._current_pnl = Decimal("0")

        super().__init__(strategy=strategy, connectors=[dca_config.exchange], update_interval=update_interval)

    async def control_task(self):
        """
        This task is responsible for creating and closing position executors
        """
        self.control_active_executors()
        if not self.close_type:
            next_executor: Optional[PositionConfig] = self._get_next_executor()
            if next_executor:
                self._create_executor(next_executor)
        else:
            self.control_shutdown_process()

    def control_active_executors(self):
        """
        This method is responsible for controlling the active executors
        """
        net_pnl = sum([executor.net_pnl for executor in self._active_executors])
        total_amount = sum([executor.amount for executor in self._active_executors])
        current_pnl_pct = net_pnl / total_amount if total_amount else Decimal("0")
        if current_pnl_pct < self._dca_config.global_stop_loss:
            self.close_type = CloseType.STOP_LOSS
            self.logger().info("Global Stop Loss Triggered!")
            for executor in self._active_executors:
                executor.early_stop()
        elif current_pnl_pct > self._dca_config.global_take_profit:
            self.close_type = CloseType.TAKE_PROFIT
            self.logger().info("Global Take Profit Triggered!")
            for executor in self._active_executors:
                executor.early_stop()
        elif not self._trailing_stop_pnl and current_pnl_pct > self._dca_config.global_trailing_stop.activation_price_delta:
            self._trailing_stop_pnl = current_pnl_pct - self._dca_config.global_trailing_stop.trailing_delta
        elif self._trailing_stop_pnl:
            if current_pnl_pct < self._trailing_stop_pnl:
                self.logger().info("Global Trailing Stop Triggered!")
                for executor in self._active_executors:
                    executor.early_stop()
            elif current_pnl_pct - self._dca_config.global_trailing_stop.trailing_delta > self._trailing_stop_pnl:
                self._trailing_stop_pnl = current_pnl_pct - self._dca_config.global_trailing_stop.trailing_delta

    def _get_next_executor(self) -> Optional[PositionConfig]:
        """
        This method is responsible for getting the next position config
        """
        current_executor_level = len(self._active_executors)
        close_price = self.get_price(connector_name=self._dca_config.exchange, trading_pair=self._dca_config.trading_pair)
        if current_executor_level < len(self._dca_config.order_levels):
            next_executor_level = self._dca_config.order_levels[current_executor_level]
            side_multiplier = -1 if next_executor_level.side == TradeType.BUY else 1
            order_price = close_price * (1 + next_executor_level.spread_factor * side_multiplier)
            if self._is_within_activation_threshold(order_price, close_price):
                return PositionConfig(
                    timestamp=self._strategy.current_timestamp,
                    trading_pair=self._dca_config.trading_pair,
                    exchange=self._dca_config.exchange,
                    amount=next_executor_level.order_amount_usd,
                    time_limit=self._dca_config.time_limit,
                    entry_price=order_price,
                    open_order_type=self._dca_config.open_order_type,
                    take_profit_order_type=self._dca_config.take_profit_order_type,
                    stop_loss_order_type=self._dca_config.stop_loss_order_type,
                    leverage=self._dca_config.leverage,
                    side=self._dca_config.side,
                )

    def _is_within_activation_threshold(self, order_price: Decimal, close_price: Decimal) -> bool:
        activation_threshold = self._dca_config.activation_threshold
        if activation_threshold:
            if self._dca_config.side == TradeType.BUY:
                return order_price < close_price * (1 - activation_threshold)
            else:
                return order_price > close_price * (1 + activation_threshold)
        else:
            return True

    def _create_executor(self, position_config: PositionConfig):
        """
        This method is responsible for creating a new position executor
        """
        self.logger().info(f"Creating new executor for {position_config}")
        self._active_executors.append(PositionExecutor(
            strategy=self._strategy,
            position_config=position_config,
        ))

    def control_shutdown_process(self):
        """
        This method is responsible for shutting down the process
        """
        all_executors_closed = all([executor.is_closed for executor in self._active_executors])
        if all_executors_closed:
            self.logger().info("All executors closed")
            self._active_executors = []
            self.terminate_control_loop()

    def early_stop(self):
        """
        This method is responsible for stopping the strategy
        """
        self.logger().info("Early stop triggered")
        self.close_type = CloseType.EARLY_STOP
        for executor in self._active_executors:
            executor.early_stop()

    def to_json(self):
        """
        Serializes the object to json
        """
        return {
            "initial_price": self._dca_config.reference_price,
            "timestamp": self._dca_config.timestamp,
            "status": self.status,
            "side": self._dca_config.side.name,
            "close_type": self.close_type.name if self.close_type else None,
            "close_timestamp": self.close_timestamp,
            "active_executors": [executor.to_json() for executor in self._active_executors],
            "amount": sum([executor.amount for executor in self._active_executors]),
            "trailing_stop_activated": self._trailing_stop_activated,
            "trailing_stop_pnl": self._trailing_stop_pnl,
            "current_pnl": self._current_pnl,
        }
