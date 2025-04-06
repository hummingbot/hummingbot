# -*- coding: utf-8 -*-
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series


def sma(close, length=None, talib=None, offset=None, **kwargs):
    """Indicator: Simple Moving Average (SMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    close = verify_series(close, max(length, min_periods))
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import SMA
        sma = SMA(close, length)
    else:
        sma = close.rolling(length, min_periods=min_periods).mean()

    # Offset
    if offset != 0:
        sma = sma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        sma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        sma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    sma.name = f"SMA_{length}"
    sma.category = "overlap"

    return sma


sma.__doc__ = \
"""Simple Moving Average (SMA)

The Simple Moving Average is the classic moving average that is the equally
weighted average over n periods.

Sources:
    https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/simple-moving-average-sma/

Calculation:
    Default Inputs:
        length=10
    SMA = SUM(close, length) / length

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    adjust (bool): Default: True
    presma (bool, optional): If True, uses SMA for initial value.
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
