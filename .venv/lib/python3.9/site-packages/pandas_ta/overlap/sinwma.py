# -*- coding: utf-8 -*-
from numpy import pi as npPi
from numpy import sin as npSin
from pandas import Series
from pandas_ta.utils import get_offset, verify_series, weights


def sinwma(close, length=None, offset=None, **kwargs):
    """Indicator: Sine Weighted Moving Average (SINWMA) by Everget of TradingView"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 14
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    sines = Series([npSin((i + 1) * npPi / (length + 1)) for i in range(0, length)])
    w = sines / sines.sum()

    sinwma = close.rolling(length, min_periods=length).apply(weights(w), raw=True)

    # Offset
    if offset != 0:
        sinwma = sinwma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        sinwma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        sinwma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    sinwma.name = f"SINWMA_{length}"
    sinwma.category = "overlap"

    return sinwma


sinwma.__doc__ = \
"""Sine Weighted Moving Average (SWMA)

A weighted average using sine cycles. The middle term(s) of the average have the
highest weight(s).

Source:
    https://www.tradingview.com/script/6MWFvnPO-Sine-Weighted-Moving-Average/
    Author: Everget (https://www.tradingview.com/u/everget/)

Calculation:
    Default Inputs:
        length=10

    def weights(w):
        def _compute(x):
            return np.dot(w * x)
        return _compute

    sines = Series([sin((i + 1) * pi / (length + 1)) for i in range(0, length)])
    w = sines / sines.sum()
    SINWMA = close.rolling(length, min_periods=length).apply(weights(w), raw=True)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
