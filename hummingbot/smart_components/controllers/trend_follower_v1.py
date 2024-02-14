import time

import pandas as pd
from pydantic import Field

from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class TrendFollowerV1Config(DirectionalTradingControllerConfigBase):
    strategy_name: str = "trend_follower_v1"
    sma_fast: int = Field(default=20, ge=10, le=150)
    sma_slow: int = Field(default=100, ge=50, le=400)
    bb_length: int = Field(default=100, ge=20, le=200)
    bb_std: float = Field(default=2.0, ge=2.0, le=3.0)
    bb_threshold: float = Field(default=0.2, ge=0.1, le=0.5)


class TrendFollowerV1(DirectionalTradingControllerBase):

    def __init__(self, config: TrendFollowerV1Config):
        super().__init__(config)
        self.config = config

    def early_stop_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        # If an executor has an active position, should we close it based on a condition. This feature is not available
        # for the backtesting yet
        return False

    def cooldown_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        # After finishing an order, the executor will be in cooldown for a certain amount of time.
        # This prevents the executor from creating a new order immediately after finishing one and execute a lot
        # of orders in a short period of time from the same side.
        if executor.close_timestamp and executor.close_timestamp + order_level.cooldown_time > time.time():
            return True
        return False

    def get_processed_data(self) -> pd.DataFrame:
        df = self.candles[0].candles_df
        df.ta.sma(length=self.config.sma_fast, append=True)
        df.ta.sma(length=self.config.sma_slow, append=True)
        df.ta.bbands(length=self.config.bb_length, std=2.0, append=True)

        # Generate long and short conditions
        bbp = df[f"BBP_{self.config.bb_length}_2.0"]
        inside_bounds_condition = (bbp < 0.5 + self.config.bb_threshold) & (bbp > 0.5 - self.config.bb_threshold)

        long_cond = (df[f'SMA_{self.config.sma_fast}'] > df[f'SMA_{self.config.sma_slow}'])
        short_cond = (df[f'SMA_{self.config.sma_fast}'] < df[f'SMA_{self.config.sma_slow}'])

        # Choose side
        df['signal'] = 0
        df.loc[long_cond & inside_bounds_condition, 'signal'] = 1
        df.loc[short_cond & inside_bounds_condition, 'signal'] = -1
        return df

    def extra_columns_to_show(self):
        return [f"BBP_{self.config.bb_length}_{self.config.bb_std}",
                f"SMA_{self.config.sma_fast}",
                f"SMA_{self.config.sma_slow}"]
