from hummingbot.smart_components.meta_strategies.market_making.market_making_strategy_base import (
    MarketMakingStrategyBase,
)
from hummingbot.smart_components.meta_strategies.meta_executor_base import MetaExecutorBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingExecutor(MetaExecutorBase):
    def __init__(self, strategy: ScriptStrategyBase, meta_strategy: MarketMakingStrategyBase, update_interval: float = 1.0):
        super().__init__(strategy, meta_strategy, update_interval)
        self.ms = meta_strategy

    def on_stop(self):
        super().on_stop()
        if self.ms.is_perpetual:
            self.close_open_positions(connector_name=self.ms.config.exchange, trading_pair=self.ms.config.trading_pair)

    def on_start(self):
        if self.ms.is_perpetual:
            self.set_leverage_and_position_mode()

    def set_leverage_and_position_mode(self):
        connector = self.strategy.connectors[self.ms.config.exchange]
        connector.set_position_mode(self.ms.config.position_mode)
        connector.set_leverage(trading_pair=self.ms.config.trading_pair, leverage=self.ms.config.leverage)

    async def control_task(self):
        if self.ms.all_candles_ready:
            for order_level in self.ms.config.order_levels:
                current_executor = self.level_executors[order_level.level_id]
                if current_executor:
                    if current_executor.is_closed:
                        if not self.ms.cooldown_condition(current_executor, order_level):
                            self.store_executor(current_executor, order_level)
                    else:
                        if self.ms.refresh_order_condition(current_executor, order_level) \
                                or self.ms.early_stop_condition(current_executor, order_level):
                            current_executor.early_stop()
                else:
                    position_config = self.ms.get_position_config(order_level)
                    self.create_executor(position_config, order_level)
