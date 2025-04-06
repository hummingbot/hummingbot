# -*- coding: utf-8 -*-
from numpy import array as npArray
from numpy import arange as npArange
from numpy import polyfit as npPolyfit
from numpy import std as npStd
from pandas import DataFrame, DatetimeIndex, Series
from .stdev import stdev as stdev
from pandas_ta.utils import get_offset, verify_series

def tos_stdevall(close, length=None, stds=None, ddof=None, offset=None, **kwargs):
    """Indicator: TD Ameritrade's Think or Swim Standard Deviation All"""
    # Validate Arguments
    stds = stds if isinstance(stds, list) and len(stds) > 0 else [1, 2, 3]
    if min(stds) <= 0: return
    if not all(i < j for i, j in zip(stds, stds[1:])):
        stds = stds[::-1]
    ddof = int(ddof) if ddof and ddof >= 0 and ddof < length else 1
    offset = get_offset(offset)

    _props = f"TOS_STDEVALL"
    if length is None:
        length = close.size
    else:
        length = int(length) if isinstance(length, int) and length > 2 else 30
        close = close.iloc[-length:]
        _props = f"{_props}_{length}"

    close = verify_series(close, length)

    if close is None: return

    # Calculate Result
    X = src_index = close.index
    if isinstance(close.index, DatetimeIndex):
        X = npArange(length)
        close = npArray(close)

    m, b = npPolyfit(X, close, 1)
    lr = Series(m * X + b, index=src_index)
    stdev = npStd(close, ddof=ddof)

    # Name and Categorize it
    df = DataFrame({f"{_props}_LR": lr}, index=src_index)
    for i in stds:
        df[f"{_props}_L_{i}"] = lr - i * stdev
        df[f"{_props}_U_{i}"] = lr + i * stdev
        df[f"{_props}_L_{i}"].name = df[f"{_props}_U_{i}"].name = f"{_props}"
        df[f"{_props}_L_{i}"].category = df[f"{_props}_U_{i}"].category = "statistics"

    # Offset
    if offset != 0:
        df = df.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        df.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        df.fillna(method=kwargs["fill_method"], inplace=True)

    # Prepare DataFrame to return
    df.name = f"{_props}"
    df.category = "statistics"

    return df


tos_stdevall.__doc__ = \
"""TD Ameritrade's Think or Swim Standard Deviation All (TOS_STDEV)

A port of TD Ameritrade's Think or Swim Standard Deviation All indicator which
returns the standard deviation of data for the entire plot or for the interval
of the last bars defined by the length parameter.

Sources:
    https://tlc.thinkorswim.com/center/reference/thinkScript/Functions/Statistical/StDevAll

Calculation:
    Default Inputs:
        length=None (All), stds=[1, 2, 3], ddof=1
    LR = Linear Regression
    STDEV = Standard Deviation

    LR = LR(close, length)
    STDEV = STDEV(close, length, ddof)
    for level in stds:
        LOWER = LR - level * STDEV
        UPPER = LR + level * STDEV

Args:
    close (pd.Series): Series of 'close's
    length (int): Bars from current bar. Default: None
    stds (list): List of Standard Deviations in increasing order from the
                 central Linear Regression line. Default: [1,2,3]
    ddof (int): Delta Degrees of Freedom.
                The divisor used in calculations is N - ddof,
                where N represents the number of elements. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: Central LR, Pairs of Lower and Upper LR Lines based on
        mulitples of the standard deviation. Default: returns 7 columns.
"""
