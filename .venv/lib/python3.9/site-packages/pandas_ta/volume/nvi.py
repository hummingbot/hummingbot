# -*- coding: utf-8 -*-
from pandas_ta.momentum import roc
from pandas_ta.utils import get_offset, signed_series, verify_series


def nvi(close, volume, length=None, initial=None, offset=None, **kwargs):
    """Indicator: Negative Volume Index (NVI)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 1
    # min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    initial = int(initial) if initial and initial > 0 else 1000
    close = verify_series(close, length)
    volume = verify_series(volume, length)
    offset = get_offset(offset)

    if close is None or volume is None: return

    # Calculate Result
    roc_ = roc(close=close, length=length)
    signed_volume = signed_series(volume, 1)
    nvi = signed_volume[signed_volume < 0].abs() * roc_
    nvi.fillna(0, inplace=True)
    nvi.iloc[0] = initial
    nvi = nvi.cumsum()

    # Offset
    if offset != 0:
        nvi = nvi.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        nvi.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        nvi.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    nvi.name = f"NVI_{length}"
    nvi.category = "volume"

    return nvi


nvi.__doc__ = \
"""Negative Volume Index (NVI)

The Negative Volume Index is a cumulative indicator that uses volume change in
an attempt to identify where smart money is active.

Sources:
    https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:negative_volume_inde
    https://www.motivewave.com/studies/negative_volume_index.htm

Calculation:
    Default Inputs:
        length=1, initial=1000
    ROC = Rate of Change

    roc = ROC(close, length)
    signed_volume = signed_series(volume, initial=1)
    nvi = signed_volume[signed_volume < 0].abs() * roc_
    nvi.fillna(0, inplace=True)
    nvi.iloc[0]= initial
    nvi = nvi.cumsum()

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
