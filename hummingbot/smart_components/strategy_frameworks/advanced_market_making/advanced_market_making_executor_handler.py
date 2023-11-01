import logging
from decimal import Decimal

from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.strategy_frameworks.advanced_market_making.advanced_market_making_controller_base import (
    AdvancedMarketMakingControllerBase,
)
from hummingbot.smart_components.strategy_frameworks.executor_handler_base import ExecutorHandlerBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AdvancedMarketMakingExecutorHandler(ExecutorHandlerBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, controller: AdvancedMarketMakingControllerBase,
                 update_interval: float = 1.0, executors_update_interval: float = 1.0):
        super().__init__(strategy, controller, update_interval, executors_update_interval)
        self.controller = controller

    def on_stop(self):
        if self.controller.is_perpetual:
            self.close_open_positions(connector_name=self.controller.config.exchange, trading_pair=self.controller.config.trading_pair)
        super().on_stop()

    def on_start(self):
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
            to_store, to_start, to_stop = self.controller.get_executors_to_store_start_stop(self.level_executors)
            for level_id in to_stop:
                executor = self.level_executors[level_id]
                executor.early_stop()
            for level_id in to_store:
                self.store_executor(self.level_executors[level_id], level_id)
            for level_id in to_start:
                position_config = self.controller.get_position_config(level_id)
                if position_config:
                    self.create_executor(position_config, level_id)
