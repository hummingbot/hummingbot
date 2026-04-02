from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class DoubleEMAV1ControllerConfig(DirectionalTradingControllerConfigBase):
    """
    Double EMA crossover strategy with ADX flat-market filter.

    Generates a long signal (1) on a golden cross (fast EMA crosses above slow EMA)
    and a short signal (-1) on a death cross (fast EMA crosses below slow EMA).
    Signals are suppressed when ADX is below adx_threshold, indicating a flat/ranging
    market where EMA crossovers tend to be unreliable.
    """
    controller_name: str = "double_ema_v1"

    # Candle data source (defaults to same connector/pair as the trading connector)
    candles_connector: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the connector for candle data, leave empty to use the trading connector: ",
            "prompt_on_new": True,
        },
    )
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trading pair for candle data, leave empty to use the trading pair: ",
            "prompt_on_new": True,
        },
    )
    interval: str = Field(
        default="1h",
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True,
        },
    )

    # EMA parameters
    fast_ema_period: int = Field(
        default=9,
        gt=0,
        json_schema_extra={
            "prompt": "Enter the fast EMA period (e.g., 9): ",
            "prompt_on_new": True,
        },
    )
    slow_ema_period: int = Field(
        default=21,
        gt=0,
        json_schema_extra={
            "prompt": "Enter the slow EMA period (e.g., 21): ",
            "prompt_on_new": True,
        },
    )

    # ADX flat-market filter
    adx_period: int = Field(
        default=14,
        gt=0,
        json_schema_extra={
            "prompt": "Enter the ADX period (e.g., 14): ",
            "prompt_on_new": True,
        },
    )
    adx_threshold: float = Field(
        default=20.0,
        gt=0,
        json_schema_extra={
            "prompt": "Enter the ADX threshold — signals below this value are skipped (e.g., 20.0): ",
            "prompt_on_new": True,
        },
    )

    # Required by BacktestingEngineBase.initialize_backtesting_data_provider() (line 117)
    candles_config: List[CandlesConfig] = Field(default_factory=list)

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

    @model_validator(mode="after")
    def build_candles_config(self) -> "DoubleEMAV1ControllerConfig":
        max_records = self.slow_ema_period * 3 + self.adx_period
        self.candles_config = [
            CandlesConfig(
                connector=self.candles_connector,
                trading_pair=self.candles_trading_pair,
                interval=self.interval,
                max_records=max_records,
            )
        ]
        return self


class DoubleEMAV1Controller(DirectionalTradingControllerBase):
    """
    Controller for the Double EMA V1 strategy.

    Uses a golden/death cross of two EMAs filtered by ADX to enter long and short
    positions. Exits are managed by the triple-barrier config (stop loss, take profit,
    time limit, optional trailing stop) from the base class.
    """

    def __init__(self, config: DoubleEMAV1ControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = config.slow_ema_period * 3 + config.adx_period
        super().__init__(config, *args, **kwargs)

    def get_candles_config(self) -> List[CandlesConfig]:
        return self.config.candles_config

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(
            connector_name=self.config.candles_connector,
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.max_records,
        )

        fast = self.config.fast_ema_period
        slow = self.config.slow_ema_period
        adx_p = self.config.adx_period

        # Calculate indicators via pandas_ta
        df.ta.ema(length=fast, append=True)    # column: EMA_{fast}
        df.ta.ema(length=slow, append=True)    # column: EMA_{slow}
        df.ta.adx(length=adx_p, append=True)   # columns: ADX_{adx_p}, DMP_{adx_p}, DMN_{adx_p}

        fast_col = f"EMA_{fast}"
        slow_col = f"EMA_{slow}"
        adx_col = f"ADX_{adx_p}"

        # Crossover detection requires previous-bar values to avoid re-triggering
        df["_fast_prev"] = df[fast_col].shift(1)
        df["_slow_prev"] = df[slow_col].shift(1)

        golden_cross = (df[fast_col] > df[slow_col]) & (df["_fast_prev"] <= df["_slow_prev"])
        death_cross = (df[fast_col] < df[slow_col]) & (df["_fast_prev"] >= df["_slow_prev"])
        is_trending = df[adx_col] >= self.config.adx_threshold

        df["signal"] = 0
        df.loc[golden_cross & is_trending, "signal"] = 1
        df.loc[death_cross & is_trending, "signal"] = -1

        valid = df.dropna(subset=[fast_col, slow_col, adx_col])
        self.processed_data["signal"] = int(valid["signal"].iloc[-1]) if not valid.empty else 0
        self.processed_data["features"] = df
