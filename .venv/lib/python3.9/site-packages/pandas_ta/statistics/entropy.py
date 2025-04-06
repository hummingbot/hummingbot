# -*- coding: utf-8 -*-
from numpy import log as npLog
from pandas_ta.utils import get_offset, verify_series


def entropy(close, length=None, base=None, offset=None, **kwargs):
    """Indicator: Entropy (ENTP)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    base = float(base) if base and base > 0 else 2.0
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    p = close / close.rolling(length).sum()
    entropy = (-p * npLog(p) / npLog(base)).rolling(length).sum()

    # Offset
    if offset != 0:
        entropy = entropy.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        entropy.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        entropy.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    entropy.name = f"ENTP_{length}"
    entropy.category = "statistics"

    return entropy


entropy.__doc__ = \
"""Entropy (ENTP)

Introduced by Claude Shannon in 1948, entropy measures the unpredictability
of the data, or equivalently, of its average information. A die has higher
entropy (p=1/6) versus a coin (p=1/2).

Sources:
    https://en.wikipedia.org/wiki/Entropy_(information_theory)

Calculation:
    Default Inputs:
        length=10, base=2

    P = close / SUM(close, length)
    E = SUM(-P * npLog(P) / npLog(base), length)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    base (float): Logarithmic Base. Default: 2
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
