from typing import List

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class TrendFollowerV1Config(DirectionalTradingControllerConfigBase):
    controller_name = "trend_follower_v1"
    candles_config: List[CandlesConfig] = []
    interval: str = Field(
        default="3m",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            prompt_on_new=False))
    sma_fast: int = Field(
        default=20,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the fast SMA period: ",
            prompt_on_new=True))
    sma_slow: int = Field(
        default=100,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the slow SMA period: ",
            prompt_on_new=True))
    bb_length: int = Field(
        default=100,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands length: ",
            prompt_on_new=True))
    bb_std: float = Field(
        default=2.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands standard deviation: ",
            prompt_on_new=False))
    bb_threshold: float = Field(
        default=0.2,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands threshold: ",
            prompt_on_new=True))


class TrendFollowerV1(DirectionalTradingControllerBase):

    def __init__(self, config: TrendFollowerV1Config, *args, **kwargs):
        self.config = config
        self.max_records = max(config.sma_fast, config.sma_slow, config.bb_length)
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.connector_name,
                trading_pair=config.trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    def get_signal(self) -> int:
        return self.get_processed_data()["signal"].iloc[-1]

    def get_processed_data(self) -> pd.DataFrame:
        df = self.market_data_provider.get_candles_df(connector_name=self.config.connector_name,
                                                      trading_pair=self.config.trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        # Add indicators
        df.ta.sma(close='close', length=self.config.sma_fast, append=True)
        df.ta.sma(close='close', length=self.config.sma_slow, append=True)
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)

        sma_fast = df[f"SMA_{self.config.sma_fast}"]
        sma_slow = df[f"SMA_{self.config.sma_slow}"]
        bb_upper = df[f"BBU_{self.config.bb_length}_{self.config.bb_std}"]
        bb_lower = df[f"BBL_{self.config.bb_length}_{self.config.bb_std}"]

        # Generate signal
        long_condition = (sma_fast > sma_slow) & (df['close'] < bb_lower + self.config.bb_threshold * (bb_upper - bb_lower))
        short_condition = (sma_fast < sma_slow) & (df['close'] > bb_upper - self.config.bb_threshold * (bb_upper - bb_lower))

        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        return df

    def to_format_status(self) -> List[str]:
        df = self.get_processed_data()
        return [format_df_for_printout(df.tail(5), table_format="psql",)]
