# -*- coding: utf-8 -*-
from pandas_ta.utils import get_offset, verify_series


def skew(close, length=None, offset=None, **kwargs):
    """Indicator: Skew"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 30
    min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    close = verify_series(close, max(length, min_periods))
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    skew = close.rolling(length, min_periods=min_periods).skew()

    # Offset
    if offset != 0:
        skew = skew.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        skew.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        skew.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    skew.name = f"SKEW_{length}"
    skew.category = "statistics"

    return skew


skew.__doc__ = \
"""Rolling Skew

Sources:

Calculation:
    Default Inputs:
        length=30
    SKEW = close.rolling(length).skew()

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 30
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
