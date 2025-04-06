# -*- coding: utf-8 -*-
from numpy import sqrt as npSqrt
from .wma import wma
from pandas_ta.utils import get_offset, verify_series


def hma(close, length=None, offset=None, **kwargs):
    """Indicator: Hull Moving Average (HMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    half_length = int(length / 2)
    sqrt_length = int(npSqrt(length))

    wmaf = wma(close=close, length=half_length)
    wmas = wma(close=close, length=length)
    hma = wma(close=2 * wmaf - wmas, length=sqrt_length)

    # Offset
    if offset != 0:
        hma = hma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        hma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        hma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    hma.name = f"HMA_{length}"
    hma.category = "overlap"

    return hma


hma.__doc__ = \
"""Hull Moving Average (HMA)

The Hull Exponential Moving Average attempts to reduce or remove lag in moving
averages.

Sources:
    https://alanhull.com/hull-moving-average

Calculation:
    Default Inputs:
        length=10
    WMA = Weighted Moving Average
    half_length = int(0.5 * length)
    sqrt_length = int(sqrt(length))

    wmaf = WMA(close, half_length)
    wmas = WMA(close, length)
    HMA = WMA(2 * wmaf - wmas, sqrt_length)

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
