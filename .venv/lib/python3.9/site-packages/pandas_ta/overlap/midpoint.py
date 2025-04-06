# -*- coding: utf-8 -*-
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series


def midpoint(close, length=None, talib=None, offset=None, **kwargs):
    """Indicator: Midpoint"""
    # Validate arguments
    length = int(length) if length and length > 0 else 2
    min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    close = verify_series(close, max(length, min_periods))
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import MIDPOINT
        midpoint = MIDPOINT(close, length)
    else:
        lowest = close.rolling(length, min_periods=min_periods).min()
        highest = close.rolling(length, min_periods=min_periods).max()
        midpoint = 0.5 * (lowest + highest)

    # Offset
    if offset != 0:
        midpoint = midpoint.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        midpoint.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        midpoint.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    midpoint.name = f"MIDPOINT_{length}"
    midpoint.category = "overlap"

    return midpoint
