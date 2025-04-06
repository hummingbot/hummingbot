# -*- coding: utf-8 -*-
from pandas_ta.overlap import sma
from pandas_ta.utils import get_offset, verify_series


def ao(high, low, fast=None, slow=None, offset=None, **kwargs):
    """Indicator: Awesome Oscillator (AO)"""
    # Validate Arguments
    fast = int(fast) if fast and fast > 0 else 5
    slow = int(slow) if slow and slow > 0 else 34
    if slow < fast:
        fast, slow = slow, fast
    _length = max(fast, slow)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    offset = get_offset(offset)

    if high is None or low is None: return

    # Calculate Result
    median_price = 0.5 * (high + low)
    fast_sma = sma(median_price, fast)
    slow_sma = sma(median_price, slow)
    ao = fast_sma - slow_sma

    # Offset
    if offset != 0:
        ao = ao.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        ao.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        ao.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    ao.name = f"AO_{fast}_{slow}"
    ao.category = "momentum"

    return ao


ao.__doc__ = \
"""Awesome Oscillator (AO)

The Awesome Oscillator is an indicator used to measure a security's momentum.
AO is generally used to affirm trends or to anticipate possible reversals.

Sources:
    https://www.tradingview.com/wiki/Awesome_Oscillator_(AO)
    https://www.ifcm.co.uk/ntx-indicators/awesome-oscillator

Calculation:
    Default Inputs:
        fast=5, slow=34
    SMA = Simple Moving Average
    median = (high + low) / 2
    AO = SMA(median, fast) - SMA(median, slow)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    fast (int): The short period. Default: 5
    slow (int): The long period. Default: 34
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
