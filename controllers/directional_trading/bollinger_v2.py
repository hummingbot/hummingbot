from sys import float_info as sflt
from typing import List

import pandas as pd
import pandas_ta as ta  # noqa: F401
import talib
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from talib import MA_Type

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class BollingerV2ControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "bollinger_v2"
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
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True})
    bb_length: int = Field(
        default=100,
        json_schema_extra={"prompt": "Enter the Bollinger Bands length: ", "prompt_on_new": True})
    bb_std: float = Field(default=2.0)
    bb_long_threshold: float = Field(default=0.0)
    bb_short_threshold: float = Field(default=1.0)

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


class BollingerV2Controller(DirectionalTradingControllerBase):
    def __init__(self, config: BollingerV2ControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = self.config.bb_length * 5
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    def non_zero_range(self, x: pd.Series, y: pd.Series) -> pd.Series:
        """Non-Zero Range

        Calculates the difference of two Series plus epsilon to any zero values.
        Technically: ```x - y + epsilon```

        Parameters:
            x (Series): Series of 'x's
            y (Series): Series of 'y's

        Returns:
            (Series): 1 column
        """
        diff = x - y
        if diff.eq(0).any().any():
            diff += sflt.epsilon
        return diff

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        # Add indicators
        df.ta.bbands(length=self.config.bb_length, lower_std=self.config.bb_std, upper_std=self.config.bb_std, append=True)
        df["upperband"], df["middleband"], df["lowerband"] = talib.BBANDS(real=df["close"], timeperiod=self.config.bb_length, nbdevup=self.config.bb_std, nbdevdn=self.config.bb_std, matype=MA_Type.SMA)

        ulr = self.non_zero_range(df["upperband"], df["lowerband"])
        bbp = self.non_zero_range(df["close"], df["lowerband"]) / ulr
        df["percent"] = bbp

        # Generate signal
        long_condition = bbp < self.config.bb_long_threshold
        short_condition = bbp > self.config.bb_short_threshold

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        # Debug
        # We skip the last row which is live candle
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', None):
            self.logger().info(df.head(-1).tail(15))

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
