from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class SmugPlugControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name = "smugplug"
    candles_config: List[CandlesConfig] = []
    candles_connector: str = Field(
        default=None)
    candles_trading_pair: str = Field(
        default=None)
    interval: str = Field(
        default="3m",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            prompt_on_new=False))
    macd_fast: int = Field(
        default=21,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the MACD fast period: ",
            prompt_on_new=True))
    macd_slow: int = Field(
        default=42,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the MACD slow period: ",
            prompt_on_new=True))
    macd_signal: int = Field(
        default=9,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the MACD signal period: ",
            prompt_on_new=True))
    # EMAs
    ema_short: int = 8
    ema_medium: int = 29
    ema_long: int = 31

    # ATR
    atr_length: int = 11
    atr_multiplier: float = 1.5

    @validator("candles_connector", pre=True, always=True)
    def set_candles_connector(cls, v, values):
        if v is None or v == "":
            return values.get("connector_name")
        return v

    @validator("candles_trading_pair", pre=True, always=True)
    def set_candles_trading_pair(cls, v, values):
        if v is None or v == "":
            return values.get("trading_pair")
        return v


class SmugPlugController(DirectionalTradingControllerBase):

    def __init__(self, config: SmugPlugControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = max(config.macd_slow, config.macd_fast, config.macd_signal, config.atr_length, config.ema_short, config.ema_medium, config.ema_long) + 20
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
        df.ta.macd(fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal, append=True)
        df.ta.atr(length=self.config.atr_length, append=True)
        df.ta.ema(length=self.config.ema_short, append=True)
        df.ta.ema(length=self.config.ema_medium, append=True)
        df.ta.ema(length=self.config.ema_long, append=True)
        df["long_atr_support"] = df["close"].shift(1) - df[f"ATRr_{self.config.atr_length}"] * self.config.atr_multiplier
        df["short_atr_resistance"] = df["close"].shift(1) + df[f"ATRr_{self.config.atr_length}"] * self.config.atr_multiplier

        macdh = df[f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"]
        short_ema = df[f"EMA_{self.config.ema_short}"]
        medium_ema = df[f"EMA_{self.config.ema_medium}"]
        long_ema = df[f"EMA_{self.config.ema_long}"]
        close = df["close"]

        long_condition = (short_ema > medium_ema) & (medium_ema > long_ema) & (close > short_ema) & (close > df["long_atr_support"]) & (macdh > 0)
        short_condition = (short_ema < medium_ema) & (medium_ema < long_ema) & (close < short_ema) & (close < df["short_atr_resistance"]) & (macdh < 0)

        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
