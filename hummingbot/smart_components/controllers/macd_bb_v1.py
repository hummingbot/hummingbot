import time
from typing import Optional

import pandas as pd
from pydantic import Field

from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class MACDBBV1Config(DirectionalTradingControllerConfigBase):
    strategy_name: str = "macd_bb_v1"
    bb_length: int = Field(default=100, ge=20, le=1000)
    bb_std: float = Field(default=2.0, ge=0.5, le=4.0)
    bb_long_threshold: float = Field(default=0.0, ge=-3.0, le=0.5)
    bb_short_threshold: float = Field(default=1.0, ge=0.5, le=3.0)
    macd_fast: int = Field(default=21, ge=2, le=100)
    macd_slow: int = Field(default=42, ge=30, le=1000)
    macd_signal: int = Field(default=9, ge=2, le=100)
    std_span: Optional[int] = None


class MACDBBV1(DirectionalTradingControllerBase):
    """
    Directional Market Making Strategy making use of NATR indicator to make spreads dynamic.
    """

    def __init__(self, config: MACDBBV1Config):
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
        df.ta.macd(fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal, append=True)
        bbp = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"]
        macdh = df[f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]
        macd = df[f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]

        # Generate signal
        long_condition = (bbp < self.config.bb_long_threshold) & (macdh > 0) & (macd < 0)
        short_condition = (bbp > self.config.bb_short_threshold) & (macdh < 0) & (macd > 0)
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        # Optional: Generate spread multiplier
        if self.config.std_span:
            df["target"] = df["close"].rolling(self.config.std_span).std() / df["close"]
        return df

    def extra_columns_to_show(self):
        return [f"BBP_{self.config.bb_length}_{self.config.bb_std}",
                f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}",
                f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]
