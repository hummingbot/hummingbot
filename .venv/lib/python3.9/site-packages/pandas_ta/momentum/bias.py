# -*- coding: utf-8 -*-
from pandas_ta.overlap import ma
from pandas_ta.utils import get_offset, verify_series


def bias(close, length=None, mamode=None, offset=None, **kwargs):
    """Indicator: Bias (BIAS)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 26
    mamode = mamode if isinstance(mamode, str) else "sma"
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    bma = ma(mamode, close, length=length, **kwargs)
    bias = (close / bma) - 1

    # Offset
    if offset != 0:
        bias = bias.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        bias.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        bias.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    bias.name = f"BIAS_{bma.name}"
    bias.category = "momentum"

    return bias


bias.__doc__ = \
"""Bias (BIAS)

Rate of change between the source and a moving average.

Sources:
    Few internet resources on definitive definition.
    Request by Github user homily, issue #46

Calculation:
    Default Inputs:
        length=26, MA='sma'

    BIAS = (close - MA(close, length)) / MA(close, length)
         = (close / MA(close, length)) - 1

Args:
    close (pd.Series): Series of 'close's
    length (int): The period. Default: 26
    mamode (str): See ```help(ta.ma)```. Default: 'sma'
    drift (int): The short period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
