# -*- coding: utf-8 -*-
from .sma import sma
from pandas_ta.utils import get_offset, verify_series


def vwma(close, volume, length=None, offset=None, **kwargs):
    """Indicator: Volume Weighted Moving Average (VWMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    close = verify_series(close, length)
    volume = verify_series(volume, length)
    offset = get_offset(offset)

    if close is None or volume is None: return

    # Calculate Result
    pv = close * volume
    vwma = sma(close=pv, length=length) / sma(close=volume, length=length)

    # Offset
    if offset != 0:
        vwma = vwma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        vwma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        vwma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    vwma.name = f"VWMA_{length}"
    vwma.category = "overlap"

    return vwma


vwma.__doc__ = \
"""Volume Weighted Moving Average (VWMA)

Volume Weighted Moving Average.

Sources:
    https://www.motivewave.com/studies/volume_weighted_moving_average.htm

Calculation:
    Default Inputs:
        length=10
    SMA = Simple Moving Average
    pv = close * volume
    VWMA = SMA(pv, length) / SMA(volume, length)

Args:
    close (pd.Series): Series of 'close's
    volume (pd.Series): Series of 'volume's
    length (int): It's period. Default: 10
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
