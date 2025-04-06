# -*- coding: utf-8 -*-
from numpy import sign as npSign
from pandas_ta.utils import get_drift, get_offset, verify_series


def psl(close, open_=None, length=None, scalar=None, drift=None, offset=None, **kwargs):
    """Indicator: Psychological Line (PSL)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 12
    scalar = float(scalar) if scalar and scalar > 0 else 100
    close = verify_series(close, length)
    drift = get_drift(drift)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    if open_ is not None:
        open_ = verify_series(open_)
        diff = npSign(close - open_)
    else:
        diff = npSign(close.diff(drift))

    diff.fillna(0, inplace=True)
    diff[diff <= 0] = 0  # Zero negative values

    psl = scalar * diff.rolling(length).sum()
    psl /= length

    # Offset
    if offset != 0:
        psl = psl.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        psl.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        psl.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = f"_{length}"
    psl.name = f"PSL{_props}"
    psl.category = "momentum"

    return psl


psl.__doc__ = \
"""Psychological Line (PSL)

The Psychological Line is an oscillator-type indicator that compares the
number of the rising periods to the total number of periods. In other
words, it is the percentage of bars that close above the previous
bar over a given period.

Sources:
    https://www.quantshare.com/item-851-psychological-line

Calculation:
    Default Inputs:
        length=12, scalar=100, drift=1

    IF NOT open:
        DIFF = SIGN(close - close[drift])
    ELSE:
        DIFF = SIGN(close - open)

    DIFF.fillna(0)
    DIFF[DIFF <= 0] = 0

    PSL = scalar * SUM(DIFF, length) / length

Args:
    close (pd.Series): Series of 'close's
    open_ (pd.Series, optional): Series of 'open's
    length (int): It's period. Default: 12
    scalar (float): How much to magnify. Default: 100
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
