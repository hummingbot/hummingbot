# -*- coding: utf-8 -*-
from .ema import ema
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series


def dema(close, length=None, talib=None, offset=None, **kwargs):
    """Indicator: Double Exponential Moving Average (DEMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    close = verify_series(close, length)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import DEMA
        dema = DEMA(close, length)
    else:
        ema1 = ema(close=close, length=length)
        ema2 = ema(close=ema1, length=length)
        dema = 2 * ema1 - ema2

    # Offset
    if offset != 0:
        dema = dema.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        dema.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        dema.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    dema.name = f"DEMA_{length}"
    dema.category = "overlap"

    return dema


dema.__doc__ = \
"""Double Exponential Moving Average (DEMA)

The Double Exponential Moving Average attempts to a smoother average with less
lag than the normal Exponential Moving Average (EMA).

Sources:
    https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/double-exponential-moving-average-dema/

Calculation:
    Default Inputs:
        length=10
    EMA = Exponential Moving Average
    ema1 = EMA(close, length)
    ema2 = EMA(ema1, length)

    DEMA = 2 * ema1 - ema2

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
