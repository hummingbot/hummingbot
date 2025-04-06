# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas import DataFrame, Series
from .ma import ma
from pandas_ta.utils import get_offset, verify_series


def hilo(high, low, close, high_length=None, low_length=None, mamode=None, offset=None, **kwargs):
    """Indicator: Gann HiLo (HiLo)"""
    # Validate Arguments
    high_length = int(high_length) if high_length and high_length > 0 else 13
    low_length = int(low_length) if low_length and low_length > 0 else 21
    mamode = mamode.lower() if isinstance(mamode, str) else "sma"
    _length = max(high_length, low_length)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    # Calculate Result
    m = close.size
    hilo = Series(npNaN, index=close.index)
    long = Series(npNaN, index=close.index)
    short = Series(npNaN, index=close.index)

    high_ma = ma(mamode, high, length=high_length)
    low_ma = ma(mamode, low, length=low_length)

    for i in range(1, m):
        if close.iloc[i] > high_ma.iloc[i - 1]:
            hilo.iloc[i] = long.iloc[i] = low_ma.iloc[i]
        elif close.iloc[i] < low_ma.iloc[i - 1]:
            hilo.iloc[i] = short.iloc[i] = high_ma.iloc[i]
        else:
            hilo.iloc[i] = hilo.iloc[i - 1]
            long.iloc[i] = short.iloc[i] = hilo.iloc[i - 1]

    # Offset
    if offset != 0:
        hilo = hilo.shift(offset)
        long = long.shift(offset)
        short = short.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        hilo.fillna(kwargs["fillna"], inplace=True)
        long.fillna(kwargs["fillna"], inplace=True)
        short.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        hilo.fillna(method=kwargs["fill_method"], inplace=True)
        long.fillna(method=kwargs["fill_method"], inplace=True)
        short.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    _props = f"_{high_length}_{low_length}"
    data = {f"HILO{_props}": hilo, f"HILOl{_props}": long, f"HILOs{_props}": short}
    df = DataFrame(data, index=close.index)

    df.name = f"HILO{_props}"
    df.category = "overlap"

    return df


hilo.__doc__ = \
"""Gann HiLo Activator(HiLo)

The Gann High Low Activator Indicator was created by Robert Krausz in a 1998
issue of Stocks & Commodities Magazine. It is a moving average based trend
indicator consisting of two different simple moving averages.

The indicator tracks both curves (of the highs and the lows). The close of the
bar defines which of the two gets plotted.

Increasing high_length and decreasing low_length better for short trades,
vice versa for long positions.

Sources:
    https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=447&Name=Gann_HiLo_Activator
    https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/simple-moving-average-sma/
    https://www.tradingview.com/script/XNQSLIYb-Gann-High-Low/

Calculation:
    Default Inputs:
        high_length=13, low_length=21, mamode="sma"
    EMA = Exponential Moving Average
    HMA = Hull Moving Average
    SMA = Simple Moving Average # Default

    if "ema":
        high_ma = EMA(high, high_length)
        low_ma = EMA(low, low_length)
    elif "hma":
        high_ma = HMA(high, high_length)
        low_ma = HMA(low, low_length)
    else: # "sma"
        high_ma = SMA(high, high_length)
        low_ma = SMA(low, low_length)

    # Similar to Supertrend MA selection
    hilo = Series(npNaN, index=close.index)
    for i in range(1, m):
        if close.iloc[i] > high_ma.iloc[i - 1]:
            hilo.iloc[i] = low_ma.iloc[i]
        elif close.iloc[i] < low_ma.iloc[i - 1]:
            hilo.iloc[i] = high_ma.iloc[i]
        else:
            hilo.iloc[i] = hilo.iloc[i - 1]

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    high_length (int): It's period. Default: 13
    low_length (int): It's period. Default: 21
    mamode (str): See ```help(ta.ma)```. Default: 'sma'
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    adjust (bool): Default: True
    presma (bool, optional): If True, uses SMA for initial value.
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: HILO (line), HILOl (long), HILOs (short) columns.
"""
