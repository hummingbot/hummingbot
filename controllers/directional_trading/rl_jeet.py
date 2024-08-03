from typing import List

import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class RLJeetControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name = "rl_jeet"
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
    max_records: int = Field(1000, client_data=ClientFieldData(prompt_on_new=False))
    q_table_path: str = "...../...../...../q_table.csv"

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


class RLJeetController(DirectionalTradingControllerBase):
    def __init__(self, config: RLJeetControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = self.config.max_records
        self.q_table = ...  # Load q table from q_table_path
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
        # Add the predicted value to the dataframe using q table
        # df contains columns = ["timestamp", "open", "high", "low", "close", "volume", "quote_asset_volume",
        #                "n_trades", "taker_buy_base_volume", "taker_buy_quote_volume"]
        # so first you will need to normalize the data to match the q table

        # Generate signal
        # if you do it vectorized, you will be able to do backtesting and live trading
        # alternatively, you can just pass add the signal to self.processed_data["signal"], where 1 is long, -1 is short, 0 is do nothing

        long_condition = ...  # condition for long signal
        short_condition = ...  # condition for short signal

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
