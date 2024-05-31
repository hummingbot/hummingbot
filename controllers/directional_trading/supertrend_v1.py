from typing import List, Optional

import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class SuperTrendConfig(DirectionalTradingControllerConfigBase):
    controller_name: str = "supertrend_v1"
    candles_config: List[CandlesConfig] = []
    candles_connector: Optional[str] = Field(default=None, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ", ))
    candles_trading_pair: Optional[str] = Field(default=None, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ", ))
    interval: str = Field(default="3m", client_data=ClientFieldData(prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ", prompt_on_new=False))
    length: int = Field(default=20, client_data=ClientFieldData(prompt=lambda mi: "Enter the supertrend length: ", prompt_on_new=True))
    multiplier: float = Field(default=4.0, client_data=ClientFieldData(prompt=lambda mi: "Enter the supertrend multiplier: ", prompt_on_new=True))
    percentage_threshold: float = Field(default=0.01, client_data=ClientFieldData(prompt=lambda mi: "Enter the percentage threshold: ", prompt_on_new=True))

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
