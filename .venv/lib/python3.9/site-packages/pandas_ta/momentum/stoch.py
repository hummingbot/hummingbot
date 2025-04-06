# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.overlap import ma
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def stoch(high, low, close, k=None, d=None, smooth_k=None, mamode=None, offset=None, **kwargs):
    """Indicator: Stochastic Oscillator (STOCH)"""
    # Validate arguments
    k = k if k and k > 0 else 14
    d = d if d and d > 0 else 3
    smooth_k = smooth_k if smooth_k and smooth_k > 0 else 3
    _length = max(k, d, smooth_k)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)
    mamode = mamode if isinstance(mamode, str) else "sma"

    if high is None or low is None or close is None: return

    # Calculate Result
    lowest_low = low.rolling(k).min()
    highest_high = high.rolling(k).max()

    stoch = 100 * (close - lowest_low)
    stoch /= non_zero_range(highest_high, lowest_low)

    stoch_k = ma(mamode, stoch.loc[stoch.first_valid_index():,], length=smooth_k)
    stoch_d = ma(mamode, stoch_k.loc[stoch_k.first_valid_index():,], length=d)

    # Offset
    if offset != 0:
        stoch_k = stoch_k.shift(offset)
        stoch_d = stoch_d.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        stoch_k.fillna(kwargs["fillna"], inplace=True)
        stoch_d.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        stoch_k.fillna(method=kwargs["fill_method"], inplace=True)
        stoch_d.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _name = "STOCH"
    _props = f"_{k}_{d}_{smooth_k}"
    stoch_k.name = f"{_name}k{_props}"
    stoch_d.name = f"{_name}d{_props}"
    stoch_k.category = stoch_d.category = "momentum"

    # Prepare DataFrame to return
    data = {stoch_k.name: stoch_k, stoch_d.name: stoch_d}
    df = DataFrame(data)
    df.name = f"{_name}{_props}"
    df.category = stoch_k.category
    return df


stoch.__doc__ = \
"""Stochastic (STOCH)

The Stochastic Oscillator (STOCH) was developed by George Lane in the 1950's.
He believed this indicator was a good way to measure momentum because changes in
momentum precede changes in price.

It is a range-bound oscillator with two lines moving between 0 and 100.
The first line (%K) displays the current close in relation to the period's
high/low range. The second line (%D) is a Simple Moving Average of the %K line.
The most common choices are a 14 period %K and a 3 period SMA for %D.

Sources:
    https://www.tradingview.com/wiki/Stochastic_(STOCH)
    https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=332&Name=KD_-_Slow

Calculation:
    Default Inputs:
        k=14, d=3, smooth_k=3
    SMA = Simple Moving Average
    LL  = low for last k periods
    HH  = high for last k periods

    STOCH = 100 * (close - LL) / (HH - LL)
    STOCHk = SMA(STOCH, smooth_k)
    STOCHd = SMA(FASTK, d)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    k (int): The Fast %K period. Default: 14
    d (int): The Slow %K period. Default: 3
    smooth_k (int): The Slow %D period. Default: 3
    mamode (str): See ```help(ta.ma)```. Default: 'sma'
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: %K, %D columns.
"""
