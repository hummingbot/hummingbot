# -*- coding: utf-8 -*-
from pandas import DataFrame
from .rsi import rsi
from pandas_ta.overlap import ma
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def stochrsi(close, length=None, rsi_length=None, k=None, d=None, mamode=None, offset=None, **kwargs):
    """Indicator: Stochastic RSI Oscillator (STOCHRSI)"""
    # Validate arguments
    length = length if length and length > 0 else 14
    rsi_length = rsi_length if rsi_length and rsi_length > 0 else 14
    k = k if k and k > 0 else 3
    d = d if d and d > 0 else 3
    close = verify_series(close, max(length, rsi_length, k, d))
    offset = get_offset(offset)
    mamode = mamode if isinstance(mamode, str) else "sma"

    if close is None: return

    # Calculate Result
    rsi_ = rsi(close, length=rsi_length)
    lowest_rsi = rsi_.rolling(length).min()
    highest_rsi = rsi_.rolling(length).max()

    stoch = 100 * (rsi_ - lowest_rsi)
    stoch /= non_zero_range(highest_rsi, lowest_rsi)

    stochrsi_k = ma(mamode, stoch, length=k)
    stochrsi_d = ma(mamode, stochrsi_k, length=d)

    # Offset
    if offset != 0:
        stochrsi_k = stochrsi_k.shift(offset)
        stochrsi_d = stochrsi_d.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        stochrsi_k.fillna(kwargs["fillna"], inplace=True)
        stochrsi_d.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        stochrsi_k.fillna(method=kwargs["fill_method"], inplace=True)
        stochrsi_d.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _name = "STOCHRSI"
    _props = f"_{length}_{rsi_length}_{k}_{d}"
    stochrsi_k.name = f"{_name}k{_props}"
    stochrsi_d.name = f"{_name}d{_props}"
    stochrsi_k.category = stochrsi_d.category = "momentum"

    # Prepare DataFrame to return
    data = {stochrsi_k.name: stochrsi_k, stochrsi_d.name: stochrsi_d}
    df = DataFrame(data)
    df.name = f"{_name}{_props}"
    df.category = stochrsi_k.category

    return df


stochrsi.__doc__ = \
"""Stochastic (STOCHRSI)

"Stochastic RSI and Dynamic Momentum Index" was created by Tushar Chande and Stanley Kroll and published in Stock & Commodities V.11:5 (189-199)

It is a range-bound oscillator with two lines moving between 0 and 100.
The first line (%K) displays the current RSI in relation to the period's
high/low range. The second line (%D) is a Simple Moving Average of the %K line.
The most common choices are a 14 period %K and a 3 period SMA for %D.

Sources:
    https://www.tradingview.com/wiki/Stochastic_(STOCH)

Calculation:
    Default Inputs:
        length=14, rsi_length=14, k=3, d=3
    RSI = Relative Strength Index
    SMA = Simple Moving Average

    RSI = RSI(high, low, close, rsi_length)
    LL  = lowest RSI for last rsi_length periods
    HH  = highest RSI for last rsi_length periods

    STOCHRSI  = 100 * (RSI - LL) / (HH - LL)
    STOCHRSIk = SMA(STOCHRSI, k)
    STOCHRSId = SMA(STOCHRSIk, d)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): The STOCHRSI period. Default: 14
    rsi_length (int): RSI period. Default: 14
    k (int): The Fast %K period. Default: 3
    d (int): The Slow %K period. Default: 3
    mamode (str): See ```help(ta.ma)```. Default: 'sma'
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: RSI %K, RSI %D columns.
"""
