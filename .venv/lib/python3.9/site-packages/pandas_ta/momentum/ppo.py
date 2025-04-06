# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta import Imports
from pandas_ta.overlap import ma
from pandas_ta.utils import get_offset, tal_ma, verify_series


def ppo(close, fast=None, slow=None, signal=None, scalar=None, mamode=None, talib=None, offset=None, **kwargs):
    """Indicator: Percentage Price Oscillator (PPO)"""
    # Validate Arguments
    fast = int(fast) if fast and fast > 0 else 12
    slow = int(slow) if slow and slow > 0 else 26
    signal = int(signal) if signal and signal > 0 else 9
    scalar = float(scalar) if scalar else 100
    mamode = mamode if isinstance(mamode, str) else "sma"
    if slow < fast:
        fast, slow = slow, fast
    close = verify_series(close, max(fast, slow, signal))
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import PPO
        ppo = PPO(close, fast, slow, tal_ma(mamode))
    else:
        fastma = ma(mamode, close, length=fast)
        slowma = ma(mamode, close, length=slow)
        ppo = scalar * (fastma - slowma)
        ppo /= slowma

    signalma = ma("ema", ppo, length=signal)
    histogram = ppo - signalma

    # Offset
    if offset != 0:
        ppo = ppo.shift(offset)
        histogram = histogram.shift(offset)
        signalma = signalma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        ppo.fillna(kwargs["fillna"], inplace=True)
        histogram.fillna(kwargs["fillna"], inplace=True)
        signalma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        ppo.fillna(method=kwargs["fill_method"], inplace=True)
        histogram.fillna(method=kwargs["fill_method"], inplace=True)
        signalma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = f"_{fast}_{slow}_{signal}"
    ppo.name = f"PPO{_props}"
    histogram.name = f"PPOh{_props}"
    signalma.name = f"PPOs{_props}"
    ppo.category = histogram.category = signalma.category = "momentum"

    # Prepare DataFrame to return
    data = {ppo.name: ppo, histogram.name: histogram, signalma.name: signalma}
    df = DataFrame(data)
    df.name = f"PPO{_props}"
    df.category = ppo.category

    return df


ppo.__doc__ = \
"""Percentage Price Oscillator (PPO)

The Percentage Price Oscillator is similar to MACD in measuring momentum.

Sources:
    https://www.tradingview.com/wiki/MACD_(Moving_Average_Convergence/Divergence)

Calculation:
    Default Inputs:
        fast=12, slow=26
    SMA = Simple Moving Average
    EMA = Exponential Moving Average
    fast_sma = SMA(close, fast)
    slow_sma = SMA(close, slow)
    PPO = 100 * (fast_sma - slow_sma) / slow_sma
    Signal = EMA(PPO, signal)
    Histogram = PPO - Signal

Args:
    close(pandas.Series): Series of 'close's
    fast(int): The short period. Default: 12
    slow(int): The long period. Default: 26
    signal(int): The signal period. Default: 9
    scalar (float): How much to magnify. Default: 100
    mamode (str): See ```help(ta.ma)```. Default: 'sma'
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset(int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: ppo, histogram, signal columns
"""
