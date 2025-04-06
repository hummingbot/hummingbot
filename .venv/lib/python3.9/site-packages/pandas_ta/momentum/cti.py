# -*- coding: utf-8 -*-
from pandas import Series
from pandas_ta.overlap import linreg
from pandas_ta.utils import get_offset, verify_series


def cti(close, length=None, offset=None, **kwargs) -> Series:
    """Indicator: Correlation Trend Indicator"""
    length = int(length) if length and length > 0 else 12
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    cti = linreg(close, length=length, r=True)

    # Offset
    if offset != 0:
        cti = cti.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        cti.fillna(method=kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        cti.fillna(method=kwargs["fill_method"], inplace=True)

    cti.name = f"CTI_{length}"
    cti.category = "momentum"
    return cti


cti.__doc__ = \
"""Correlation Trend Indicator (CTI)

The Correlation Trend Indicator is an oscillator created by John Ehler in 2020.
It assigns a value depending on how close prices in that range are to following
a positively- or negatively-sloping straight line. Values range from -1 to 1.
This is a wrapper for ta.linreg(close, r=True).

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 12
    offset (int): How many periods to offset the result. Default: 0

Returns:
    pd.Series: Series of the CTI values for the given period.
"""
