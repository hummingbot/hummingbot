from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class SuperTrendConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "supertrend_v1"
    candles_config: List[CandlesConfig] = []
    candles_connector: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",
            "prompt_on_new": True})
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",
            "prompt_on_new": True})
    interval: str = Field(
        default="3m",
        json_schema_extra={"prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ", "prompt_on_new": True})
    length: int = Field(
        default=20,
        json_schema_extra={"prompt": "Enter the supertrend length: ", "prompt_on_new": True})
    multiplier: float = Field(
        default=4.0,
        json_schema_extra={"prompt": "Enter the supertrend multiplier: ", "prompt_on_new": True})
    percentage_threshold: float = Field(
        default=0.01,
        json_schema_extra={"prompt": "Enter the percentage threshold: ", "prompt_on_new": True})

    @field_validator("candles_connector", mode="before")
    @classmethod
    def set_candles_connector(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("connector_name")
        return v

    @field_validator("candles_trading_pair", mode="before")
    @classmethod
    def set_candles_trading_pair(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("trading_pair")
        return v


class SuperTrend(DirectionalTradingControllerBase):
    def __init__(self, config: SuperTrendConfig, *args, **kwargs):
        self.config = config
        self.max_records = config.length + 10
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        # Add indicators
        df.ta.supertrend(length=self.config.length, multiplier=self.config.multiplier, append=True)
        df["percentage_distance"] = abs(df["close"] - df[f"SUPERT_{self.config.length}_{self.config.multiplier}"]) / df["close"]

        # Generate long and short conditions
        long_condition = (df[f"SUPERTd_{self.config.length}_{self.config.multiplier}"] == 1) & (df["percentage_distance"] < self.config.percentage_threshold)
        short_condition = (df[f"SUPERTd_{self.config.length}_{self.config.multiplier}"] == -1) & (df["percentage_distance"] < self.config.percentage_threshold)

        # Choose side
        df['signal'] = 0
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
