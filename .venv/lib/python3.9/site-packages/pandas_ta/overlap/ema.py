# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series


def ema(close, length=None, talib=None, offset=None, **kwargs):
    """Indicator: Exponential Moving Average (EMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    adjust = kwargs.pop("adjust", False)
    sma = kwargs.pop("sma", True)
    close = verify_series(close, length)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import EMA
        ema = EMA(close, length)
    else:
        if sma:
            close = close.copy()
            sma_nth = close[0:length].mean()
            close[:length - 1] = npNaN
            close.iloc[length - 1] = sma_nth
        ema = close.ewm(span=length, adjust=adjust).mean()

    # Offset
    if offset != 0:
        ema = ema.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        ema.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        ema.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    ema.name = f"EMA_{length}"
    ema.category = "overlap"

    return ema


ema.__doc__ = \
"""Exponential Moving Average (EMA)

The Exponential Moving Average is more responsive moving average compared to the
Simple Moving Average (SMA).  The weights are determined by alpha which is
proportional to it's length.  There are several different methods of calculating
EMA.  One method uses just the standard definition of EMA and another uses the
SMA to generate the initial value for the rest of the calculation.

Sources:
    https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:moving_averages
    https://www.investopedia.com/ask/answers/122314/what-exponential-moving-average-ema-formula-and-how-ema-calculated.asp

Calculation:
    Default Inputs:
        length=10, adjust=False, sma=True
    if sma:
        sma_nth = close[0:length].sum() / length
        close[:length - 1] = np.NaN
        close.iloc[length - 1] = sma_nth
    EMA = close.ewm(span=length, adjust=adjust).mean()

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    adjust (bool, optional): Default: False
    sma (bool, optional): If True, uses SMA for initial value. Default: True
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
