# -*- coding: utf-8 -*-
from pandas_ta.utils import get_offset, symmetric_triangle, verify_series, weights


def swma(close, length=None, asc=None, offset=None, **kwargs):
    """Indicator: Symmetric Weighted Moving Average (SWMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    # min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    asc = asc if asc else True
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    triangle = symmetric_triangle(length, weighted=True)
    swma = close.rolling(length, min_periods=length).apply(weights(triangle), raw=True)
    # swma = close.rolling(length).apply(weights(triangle), raw=True)

    # Offset
    if offset != 0:
        swma = swma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        swma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        swma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    swma.name = f"SWMA_{length}"
    swma.category = "overlap"

    return swma


swma.__doc__ = \
"""Symmetric Weighted Moving Average (SWMA)

Symmetric Weighted Moving Average where weights are based on a symmetric
triangle.  For example: n=3 -> [1, 2, 1], n=4 -> [1, 2, 2, 1], etc...
This moving average has variable length in contrast to TradingView's fixed
length of 4.

Source:
    https://www.tradingview.com/study-script-reference/#fun_swma

Calculation:
    Default Inputs:
        length=10

    def weights(w):
        def _compute(x):
            return np.dot(w * x)
        return _compute

    triangle = utils.symmetric_triangle(length - 1)
    SWMA = close.rolling(length)_.apply(weights(triangle), raw=True)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    asc (bool): Recent values weigh more. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
