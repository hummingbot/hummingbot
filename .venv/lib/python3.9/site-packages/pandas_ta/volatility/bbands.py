# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta import Imports
from pandas_ta.overlap import ma
from pandas_ta.statistics import stdev
from pandas_ta.utils import get_offset, non_zero_range, tal_ma, verify_series


def bbands(close, length=None, std=None, ddof=0, mamode=None, talib=None, offset=None, **kwargs):
    """Indicator: Bollinger Bands (BBANDS)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 5
    std = float(std) if std and std > 0 else 2.0
    mamode = mamode if isinstance(mamode, str) else "sma"
    ddof = int(ddof) if ddof >= 0 and ddof < length else 1
    close = verify_series(close, length)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import BBANDS
        upper, mid, lower = BBANDS(close, length, std, std, tal_ma(mamode))
    else:
        standard_deviation = stdev(close=close, length=length, ddof=ddof)
        deviations = std * standard_deviation
        # deviations = std * standard_deviation.loc[standard_deviation.first_valid_index():,]

        mid = ma(mamode, close, length=length, **kwargs)
        lower = mid - deviations
        upper = mid + deviations

    ulr = non_zero_range(upper, lower)
    bandwidth = 100 * ulr / mid
    percent = non_zero_range(close, lower) / ulr

    # Offset
    if offset != 0:
        lower = lower.shift(offset)
        mid = mid.shift(offset)
        upper = upper.shift(offset)
        bandwidth = bandwidth.shift(offset)
        percent = bandwidth.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        lower.fillna(kwargs["fillna"], inplace=True)
        mid.fillna(kwargs["fillna"], inplace=True)
        upper.fillna(kwargs["fillna"], inplace=True)
        bandwidth.fillna(kwargs["fillna"], inplace=True)
        percent.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        lower.fillna(method=kwargs["fill_method"], inplace=True)
        mid.fillna(method=kwargs["fill_method"], inplace=True)
        upper.fillna(method=kwargs["fill_method"], inplace=True)
        bandwidth.fillna(method=kwargs["fill_method"], inplace=True)
        percent.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    lower.name = f"BBL_{length}_{std}"
    mid.name = f"BBM_{length}_{std}"
    upper.name = f"BBU_{length}_{std}"
    bandwidth.name = f"BBB_{length}_{std}"
    percent.name = f"BBP_{length}_{std}"
    upper.category = lower.category = "volatility"
    mid.category = bandwidth.category = upper.category

    # Prepare DataFrame to return
    data = {
        lower.name: lower, mid.name: mid, upper.name: upper,
        bandwidth.name: bandwidth, percent.name: percent
    }
    bbandsdf = DataFrame(data)
    bbandsdf.name = f"BBANDS_{length}_{std}"
    bbandsdf.category = mid.category

    return bbandsdf


bbands.__doc__ = \
"""Bollinger Bands (BBANDS)

A popular volatility indicator by John Bollinger.

Sources:
    https://www.tradingview.com/wiki/Bollinger_Bands_(BB)

Calculation:
    Default Inputs:
        length=5, std=2, mamode="sma", ddof=0
    EMA = Exponential Moving Average
    SMA = Simple Moving Average
    STDEV = Standard Deviation
    stdev = STDEV(close, length, ddof)
    if "ema":
        MID = EMA(close, length)
    else:
        MID = SMA(close, length)

    LOWER = MID - std * stdev
    UPPER = MID + std * stdev

    BANDWIDTH = 100 * (UPPER - LOWER) / MID
    PERCENT = (close - LOWER) / (UPPER - LOWER)

Args:
    close (pd.Series): Series of 'close's
    length (int): The short period. Default: 5
    std (int): The long period. Default: 2
    ddof (int): Degrees of Freedom to use. Default: 0
    mamode (str): See ```help(ta.ma)```. Default: 'sma'
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: lower, mid, upper, bandwidth, and percent columns.
"""
