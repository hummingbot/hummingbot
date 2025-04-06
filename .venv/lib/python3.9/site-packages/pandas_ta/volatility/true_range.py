# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas import concat
from pandas_ta import Imports
from pandas_ta.utils import get_drift, get_offset, non_zero_range, verify_series


def true_range(high, low, close, talib=None, drift=None, offset=None, **kwargs):
    """Indicator: True Range"""
    # Validate arguments
    high = verify_series(high)
    low = verify_series(low)
    close = verify_series(close)
    drift = get_drift(drift)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import TRANGE
        true_range = TRANGE(high, low, close)
    else:
        high_low_range = non_zero_range(high, low)
        prev_close = close.shift(drift)
        ranges = [high_low_range, high - prev_close, prev_close - low]
        true_range = concat(ranges, axis=1)
        true_range = true_range.abs().max(axis=1)
        true_range.iloc[:drift] = npNaN

    # Offset
    if offset != 0:
        true_range = true_range.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        true_range.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        true_range.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    true_range.name = f"TRUERANGE_{drift}"
    true_range.category = "volatility"

    return true_range


true_range.__doc__ = \
"""True Range

An method to expand a classical range (high minus low) to include
possible gap scenarios.

Sources:
    https://www.macroption.com/true-range/

Calculation:
    Default Inputs:
        drift=1
    ABS = Absolute Value
    prev_close = close.shift(drift)
    TRUE_RANGE = ABS([high - low, high - prev_close, low - prev_close])

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    drift (int): The shift period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature
"""
