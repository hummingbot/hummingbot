import time

import pandas as pd
import pandas_ta as ta  # noqa: F401
from pydantic import Field

from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class BollingerV1Config(DirectionalTradingControllerConfigBase):
    strategy_name = "bollinger_v1"
    bb_length: int = Field(default=100, ge=20, le=400)
    bb_std: float = Field(default=2.0, ge=2.0, le=3.0)
    bb_long_threshold: float = Field(default=0.0, ge=-2.0, le=0.5)
    bb_short_threshold: float = Field(default=1.0, ge=0.5, le=3.0)


class BollingerV1(DirectionalTradingControllerBase):

    def __init__(self, config: BollingerV1Config):
        super().__init__(config)
        self.config = config

    def early_stop_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        """
        If an executor has an active position, should we close it based on a condition.
        """
        return False

    def cooldown_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        """
        After finishing an order, the executor will be in cooldown for a certain amount of time.
        This prevents the executor from creating a new order immediately after finishing one and execute a lot
        of orders in a short period of time from the same side.
        """
        if executor.close_timestamp and executor.close_timestamp + order_level.cooldown_time > time.time():
            return True
        return False

    def get_processed_data(self) -> pd.DataFrame:
        df = self.candles[0].candles_df

        # Add indicators
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)

        # Generate signal
        long_condition = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"] < self.config.bb_long_threshold
        short_condition = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"] > self.config.bb_short_threshold

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1
        return df

    def extra_columns_to_show(self):
        return [f"BBP_{self.config.bb_length}_{self.config.bb_std}"]
