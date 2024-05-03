from typing import List

from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class TrendFollowerV1Config(DirectionalTradingControllerConfigBase):
    controller_name = "trend_follower_v1"
    candles_config: List[CandlesConfig] = []
    candles_connector: str = Field(
        default=None,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ", )
    )
    candles_trading_pair: str = Field(
        default=None,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ", )
    )
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


class TrendFollowerV1(DirectionalTradingControllerBase):

    def __init__(self, config: TrendFollowerV1Config, *args, **kwargs):
        self.config = config
        self.max_records = max(config.sma_fast, config.sma_slow, config.bb_length)
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
        df.ta.sma(close='close', length=self.config.sma_fast, append=True)
        df.ta.sma(close='close', length=self.config.sma_slow, append=True)
        df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std, append=True)

        sma_fast = df[f"SMA_{self.config.sma_fast}"]
        sma_slow = df[f"SMA_{self.config.sma_slow}"]

        # Generate signal
        long_condition = (sma_fast > sma_slow)
        short_condition = (sma_fast < sma_slow)

        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
