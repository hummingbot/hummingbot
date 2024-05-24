from itertools import chain
from math import pi

import numpy as np
import pandas as pd
import pandas_ta as ta


class Features:
    def __init__(self, external_features = {}, df = pd.DataFrame()):
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
