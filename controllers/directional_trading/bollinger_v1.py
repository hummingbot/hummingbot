from typing import List

import pandas as pd
import pandas_ta as ta  # noqa: F401
from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class BollingerV1ControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name = "bollinger_v1"
    candles_config: List[CandlesConfig] = []
    interval: str = Field(
        default="3m",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            prompt_on_new=False))
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
    bb_long_threshold: float = Field(
        default=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands long threshold: ",
            prompt_on_new=True))
    bb_short_threshold: float = Field(
        default=1.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands short threshold: ",
            prompt_on_new=True))


class BollingerV1Controller(DirectionalTradingControllerBase):

    def __init__(self, config: BollingerV1ControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = self.config.bb_length
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
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)

        # Generate signal
        long_condition = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"] < self.config.bb_long_threshold
        short_condition = df[f"BBP_{self.config.bb_length}_{self.config.bb_std}"] > self.config.bb_short_threshold

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1
        return df

    def to_format_status(self) -> List[str]:
        df = self.get_processed_data()
        return [format_df_for_printout(df.tail(5), table_format="psql", )]
