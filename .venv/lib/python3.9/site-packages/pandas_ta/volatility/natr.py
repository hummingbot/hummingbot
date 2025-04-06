# -*- coding: utf-8 -*-
from .atr import atr
from pandas_ta import Imports
from pandas_ta.utils import get_drift, get_offset, verify_series


def natr(high, low, close, length=None, scalar=None, mamode=None, talib=None, drift=None, offset=None, **kwargs):
    """Indicator: Normalized Average True Range (NATR)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 14
    mamode = mamode if isinstance(mamode, str) else "ema"
    scalar = float(scalar) if scalar else 100
    high = verify_series(high, length)
    low = verify_series(low, length)
    close = verify_series(close, length)
    drift = get_drift(drift)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if high is None or low is None or close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import NATR
        natr = NATR(high, low, close, length)
    else:
        natr = scalar / close
        natr *= atr(high=high, low=low, close=close, length=length, mamode=mamode, drift=drift, offset=offset, **kwargs)

    # Offset
    if offset != 0:
        natr = natr.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        natr.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        natr.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    natr.name = f"NATR_{length}"
    natr.category = "volatility"

    return natr


natr.__doc__ = \
"""Normalized Average True Range (NATR)

Normalized Average True Range attempt to normalize the average true range.

Sources:
    https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/normalized-average-true-range-natr/

Calculation:
    Default Inputs:
        length=20
    ATR = Average True Range
    NATR = (100 / close) * ATR(high, low, close)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): The short period. Default: 20
    scalar (float): How much to magnify. Default: 100
    mamode (str): See ```help(ta.ma)```. Default: 'ema'
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature
"""
