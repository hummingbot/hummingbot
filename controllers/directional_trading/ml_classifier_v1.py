import pickle
from typing import List

import numpy as np
import pandas as pd
import pandas_ta as ta  # noqa: F401
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class MLClassifierV1ControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name = "ml_classifier_v1"
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
    model_path: str = Field(
        default="/models/ml_classifier_v1.pkl",
        client_data=ClientFieldData(
            prompt_on_new=False)
    )

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


class Features:
    def __init__(self, external_features={}, df=pd.DataFrame()):
        self.external_features = external_features
        self.df = df

    def add_features(self, dropna=True):
        for key, value in self.external_features.items():
            drop = False
            for k, v in value.items():
                if k == "macd":
                    for l in v:
                        columns = self.df.columns
                        if key != "close":
                            self.df.rename(columns={key: "close"}, inplace=True)
                            self.df.ta.macd(fast=l[0], slow=l[1], signal=l[2], append=True)
                            self.df.rename(columns={"close": key}, inplace=True)
                        else:
                            self.df.ta.macd(fast=l[0], slow=l[1], signal=l[2], append=True)
                        new_cols = [c for c in self.df.columns if c not in columns]
                        for col in new_cols:
                            self.df.rename(columns={col: col + "_" + key}, inplace=True)
                elif k == "rsi":
                    for l in v:
                        columns = self.df.columns
                        if key != "close":
                            self.df.rename(columns={key: "close"}, inplace=True)
                            self.df.ta.rsi(length=l, append=True)
                            self.df.rename(columns={"close": key}, inplace=True)
                        else:
                            self.df.ta.rsi(length=l, append=True)
                        new_cols = [c for c in self.df.columns if c not in columns]
                        for col in new_cols:
                            self.df.rename(columns={col: col + "_" + key}, inplace=True)
                elif k == "bbands":
                    for l in v:
                        columns = self.df.columns
                        if key != "close":
                            self.df.rename(columns={key: "close"}, inplace=True)
                            self.df.ta.bbands(length=l[0], std=l[1], mamode=l[2], append=True)
                            self.df.rename(columns={"close": key}, inplace=True)
                        else:
                            self.df.ta.bbands(length=l[0], std=l[1], mamode=l[2], append=True)
                        new_cols = [c for c in self.df.columns if c not in columns]
                        for col in new_cols:
                            self.df.rename(columns={col: col + "_" + key}, inplace=True)
                elif k == "relative_changes":
                    for l in v:
                        self.df[key + '_relative_changes_' + str(l)] = self.df[key].pct_change(periods = l)
                elif k == "mov_avg":
                    self.add_moving_averages(column_name=key, windows=v)
                elif k == "lag":
                    self.add_lagged_values(column_name=key, lags=v)
                elif k == "volatility":
                    self.add_volatility_measures(column_name=key, windows=v)
                elif k == "drop":
                    drop = v

            if drop:
                self.df.drop(columns=key, inplace=True)

        if dropna:
            self.df.dropna()

        return self.df

    def add_moving_averages(self, column_name, windows=[7, 14, 30]):
        for window in windows:
            self.df[f'MA_{column_name}_{window}'] = self.df[column_name].rolling(window=window).mean()

    def add_lagged_values(self, column_name, lags=[1, 2, 3]):
        for lag in lags:
            self.df[f'{column_name}_lag_{lag}'] = self.df[column_name].shift(lag)

    def add_volatility_measures(self, column_name, windows=[7, 14, 30]):
        for window in windows:
            self.df[f'{column_name}_volatility_{window}'] = self.df[column_name].pct_change().rolling(window=window).std() * np.sqrt(window)


class MLClassifierV1Controller(DirectionalTradingControllerBase):

    def __init__(self, config: MLClassifierV1ControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = 5000
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        with open(self.config.model_path, 'rb') as f:
            self.model = pickle.load(f)
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self) -> pd.DataFrame:
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        df["target"] = df["close"].rolling(100).std() / df["close"]
        df["signal"] = 1
        pipe = self.model['pipeline']
        extra_features = self.model['extra_features']
        feat = Features(df=df, external_features=extra_features)
        df = feat.add_features()
        df.dropna(inplace=True)
        predictions = pipe.predict(df)
        # Generate signal
        df["signal"] = predictions
        df["signal"] = df['signal'].rolling(window=5).mean().round(0)
        self.processed_data = {
            "signal": df["signal"].iloc[-1],
            "features": df
        }
