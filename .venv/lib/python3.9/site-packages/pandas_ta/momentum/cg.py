# -*- coding: utf-8 -*-
from pandas_ta.utils import get_offset, verify_series, weights


def cg(close, length=None, offset=None, **kwargs):
    """Indicator: Center of Gravity (CG)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    coefficients = [length - i for i in range(0, length)]
    numerator = -close.rolling(length).apply(weights(coefficients), raw=True)
    cg = numerator / close.rolling(length).sum()

    # Offset
    if offset != 0:
        cg = cg.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        cg.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        cg.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    cg.name = f"CG_{length}"
    cg.category = "momentum"

    return cg


cg.__doc__ = \
"""Center of Gravity (CG)

The Center of Gravity Indicator by John Ehlers attempts to identify turning
points while exhibiting zero lag and smoothing.

Sources:
    http://www.mesasoftware.com/papers/TheCGOscillator.pdf

Calculation:
    Default Inputs:
        length=10

Args:
    close (pd.Series): Series of 'close's
    length (int): The length of the period. Default: 10
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
