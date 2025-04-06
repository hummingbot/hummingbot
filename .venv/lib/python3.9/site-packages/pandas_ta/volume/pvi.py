# -*- coding: utf-8 -*-
from pandas_ta.momentum import roc
from pandas_ta.utils import get_offset, signed_series, verify_series


def pvi(close, volume, length=None, initial=None, offset=None, **kwargs):
    """Indicator: Positive Volume Index (PVI)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 1
    # min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    initial = int(initial) if initial and initial > 0 else 1000
    close = verify_series(close, length)
    volume = verify_series(volume, length)
    offset = get_offset(offset)

    if close is None or volume is None: return

    # Calculate Result
    signed_volume = signed_series(volume, 1)
    pvi = roc(close=close, length=length) * signed_volume[signed_volume > 0].abs()
    pvi.fillna(0, inplace=True)
    pvi.iloc[0] = initial
    pvi = pvi.cumsum()

    # Offset
    if offset != 0:
        pvi = pvi.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        pvi.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        pvi.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    pvi.name = f"PVI_{length}"
    pvi.category = "volume"

    return pvi


pvi.__doc__ = \
"""Positive Volume Index (PVI)

The Positive Volume Index is a cumulative indicator that uses volume change in
an attempt to identify where smart money is active.
Used in conjunction with NVI.

Sources:
    https://www.investopedia.com/terms/p/pvi.asp

Calculation:
    Default Inputs:
        length=1, initial=1000
    ROC = Rate of Change

    roc = ROC(close, length)
    signed_volume = signed_series(volume, initial=1)
    pvi = signed_volume[signed_volume > 0].abs() * roc_
    pvi.fillna(0, inplace=True)
    pvi.iloc[0]= initial
    pvi = pvi.cumsum()

Args:
    close (pd.Series): Series of 'close's
    volume (pd.Series): Series of 'volume's
    length (int): The short period. Default: 13
    initial (int): The short period. Default: 1000
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
