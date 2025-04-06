"""
.. module:: utils
   :synopsis: Utils classes and functions.

.. moduleauthor:: Dario Lopez Padial (Bukosabino)

"""
import math

import numpy as np
import pandas as pd


class IndicatorMixin:
    """Util mixin indicator class"""

    _fillna = False

    def _check_fillna(self, series: pd.Series, value: int = 0) -> pd.Series:
        """Check if fillna flag is True.

        Args:
            series(pandas.Series): calculated indicator series.
            value(int): value to fill gaps; if -1 fill values using 'backfill' mode.

        Returns:
            pandas.Series: New feature generated.
        """
        if self._fillna:
            series_output = series.copy(deep=False)
            series_output = series_output.replace([np.inf, -np.inf], np.nan)
            if isinstance(value, int) and value == -1:
                series = series_output.ffill().bfill()
            else:
                series = series_output.ffill().fillna(value)
        return series

    @staticmethod
    def _true_range(
        high: pd.Series, low: pd.Series, prev_close: pd.Series
    ) -> pd.Series:
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.DataFrame(data={"tr1": tr1, "tr2": tr2, "tr3": tr3}).max(axis=1)
        return true_range


def dropna(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with "Nans" values"""
    df = df.copy()
    number_cols = df.select_dtypes(include=np.number).columns.tolist()
    df[number_cols] = df[number_cols][df[number_cols] < math.exp(709)]  # big number
    df[number_cols] = df[number_cols][df[number_cols] != 0.0]
    df = df.dropna()
    return df


def _sma(series, periods: int, fillna: bool = False):
    min_periods = 0 if fillna else periods
    return series.rolling(window=periods, min_periods=min_periods).mean()


def _ema(series, periods: int, fillna: bool = False):
    min_periods = 0 if fillna else periods
    return series.ewm(span=periods, min_periods=min_periods, adjust=False).mean()


def _get_min_max(series1: pd.Series, series2: pd.Series, function: str = "min"):
    """Find min or max value between two lists for each index"""
    series1 = np.array(series1)
    series2 = np.array(series2)
    if function == "min":
        output = np.amin([series1, series2], axis=0)
    elif function == "max":
        output = np.amax([series1, series2], axis=0)
    else:
        raise ValueError('"f" variable value should be "min" or "max"')

    return pd.Series(output)
