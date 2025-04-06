# -*- coding: utf-8 -*-
from pandas import Series
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series


def wma(close, length=None, asc=None, talib=None, offset=None, **kwargs):
    """Indicator: Weighted Moving Average (WMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    asc = asc if asc else True
    close = verify_series(close, length)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import WMA
        wma = WMA(close, length)
    else:
        from numpy import arange as npArange
        from numpy import dot as npDot

        total_weight = 0.5 * length * (length + 1)
        weights_ = Series(npArange(1, length + 1))
        weights = weights_ if asc else weights_[::-1]

        def linear(w):
            def _compute(x):
                return npDot(x, w) / total_weight
            return _compute

        close_ = close.rolling(length, min_periods=length)
        wma = close_.apply(linear(weights), raw=True)

    # Offset
    if offset != 0:
        wma = wma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        wma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        wma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    wma.name = f"WMA_{length}"
    wma.category = "overlap"

    return wma


wma.__doc__ = \
"""Weighted Moving Average (WMA)

The Weighted Moving Average where the weights are linearly increasing and
the most recent data has the heaviest weight.

Sources:
    https://en.wikipedia.org/wiki/Moving_average#Weighted_moving_average

Calculation:
    Default Inputs:
        length=10, asc=True
    total_weight = 0.5 * length * (length + 1)
    weights_ = [1, 2, ..., length + 1]  # Ascending
    weights = weights if asc else weights[::-1]

    def linear_weights(w):
        def _compute(x):
            return (w * x).sum() / total_weight
        return _compute

    WMA = close.rolling(length)_.apply(linear_weights(weights), raw=True)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    asc (bool): Recent values weigh more. Default: True
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
