# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.utils import get_offset, verify_series


def donchian(high, low, lower_length=None, upper_length=None, offset=None, **kwargs):
    """Indicator: Donchian Channels (DC)"""
    # Validate arguments
    lower_length = int(lower_length) if lower_length and lower_length > 0 else 20
    upper_length = int(upper_length) if upper_length and upper_length > 0 else 20
    lower_min_periods = int(kwargs["lower_min_periods"]) if "lower_min_periods" in kwargs and kwargs["lower_min_periods"] is not None else lower_length
    upper_min_periods = int(kwargs["upper_min_periods"]) if "upper_min_periods" in kwargs and kwargs["upper_min_periods"] is not None else upper_length
    _length = max(lower_length, lower_min_periods, upper_length, upper_min_periods)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    offset = get_offset(offset)

    if high is None or low is None: return

    # Calculate Result
    lower = low.rolling(lower_length, min_periods=lower_min_periods).min()
    upper = high.rolling(upper_length, min_periods=upper_min_periods).max()
    mid = 0.5 * (lower + upper)

    # Handle fills
    if "fillna" in kwargs:
        lower.fillna(kwargs["fillna"], inplace=True)
        mid.fillna(kwargs["fillna"], inplace=True)
        upper.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        lower.fillna(method=kwargs["fill_method"], inplace=True)
        mid.fillna(method=kwargs["fill_method"], inplace=True)
        upper.fillna(method=kwargs["fill_method"], inplace=True)

    # Offset
    if offset != 0:
        lower = lower.shift(offset)
        mid = mid.shift(offset)
        upper = upper.shift(offset)

    # Name and Categorize it
    lower.name = f"DCL_{lower_length}_{upper_length}"
    mid.name = f"DCM_{lower_length}_{upper_length}"
    upper.name = f"DCU_{lower_length}_{upper_length}"
    mid.category = upper.category = lower.category = "volatility"

    # Prepare DataFrame to return
    data = {lower.name: lower, mid.name: mid, upper.name: upper}
    dcdf = DataFrame(data)
    dcdf.name = f"DC_{lower_length}_{upper_length}"
    dcdf.category = mid.category

    return dcdf


donchian.__doc__ = \
"""Donchian Channels (DC)

Donchian Channels are used to measure volatility, similar to
Bollinger Bands and Keltner Channels.

Sources:
    https://www.tradingview.com/wiki/Donchian_Channels_(DC)

Calculation:
    Default Inputs:
        lower_length=upper_length=20
    LOWER = low.rolling(lower_length).min()
    UPPER = high.rolling(upper_length).max()
    MID = 0.5 * (LOWER + UPPER)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    lower_length (int): The short period. Default: 20
    upper_length (int): The short period. Default: 20
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: lower, mid, upper columns.
"""
