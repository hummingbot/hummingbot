# -*- coding: utf-8 -*-
from numpy import fabs as npFabs
from pandas_ta.utils import get_drift, get_offset, non_zero_range, verify_series


def vhf(close, length=None, drift=None, offset=None, **kwargs):
    """Indicator: Vertical Horizontal Filter (VHF)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 28
    close = verify_series(close, length)
    drift = get_drift(drift)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    hcp = close.rolling(length).max()
    lcp = close.rolling(length).min()
    diff = npFabs(close.diff(drift))
    vhf  = npFabs(non_zero_range(hcp, lcp)) / diff.rolling(length).sum()

    # Offset
    if offset != 0:
        vhf = vhf.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        vhf.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        vhf.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    vhf.name = f"VHF_{length}"
    vhf.category = "trend"

    return vhf


vhf.__doc__ = \
"""Vertical Horizontal Filter (VHF)

VHF was created by Adam White to identify trending and ranging markets.

Sources:
    https://www.incrediblecharts.com/indicators/vertical_horizontal_filter.php

Calculation:
    Default Inputs:
        length = 28
    HCP = Highest Close Price in Period
    LCP = Lowest Close Price in Period
    Change = abs(Ct - Ct-1)
    VHF = (HCP - LCP) / RollingSum[length] of Change

Args:
    source (pd.Series): Series of prices (usually close).
    length (int): The period length. Default: 28
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
