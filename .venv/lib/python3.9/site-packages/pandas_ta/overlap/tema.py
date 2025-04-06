# -*- coding: utf-8 -*-
from .ema import ema
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series


def tema(close, length=None, talib=None, offset=None, **kwargs):
    """Indicator: Triple Exponential Moving Average (TEMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    close = verify_series(close, length)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import TEMA
        tema = TEMA(close, length)
    else:
        ema1 = ema(close=close, length=length, **kwargs)
        ema2 = ema(close=ema1, length=length, **kwargs)
        ema3 = ema(close=ema2, length=length, **kwargs)
        tema = 3 * (ema1 - ema2) + ema3

    # Offset
    if offset != 0:
        tema = tema.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        tema.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        tema.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    tema.name = f"TEMA_{length}"
    tema.category = "overlap"

    return tema


tema.__doc__ = \
"""Triple Exponential Moving Average (TEMA)

A less laggy Exponential Moving Average.

Sources:
    https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/triple-exponential-moving-average-tema/

Calculation:
    Default Inputs:
        length=10
    EMA = Exponential Moving Average
    ema1 = EMA(close, length)
    ema2 = EMA(ema1, length)
    ema3 = EMA(ema2, length)
    TEMA = 3 * (ema1 - ema2) + ema3

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    adjust (bool): Default: True
    presma (bool, optional): If True, uses SMA for initial value.
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
