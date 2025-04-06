# -*- coding: utf-8 -*-
from pandas_ta.overlap import ma
from pandas_ta.statistics import stdev
from pandas_ta.utils import get_drift, get_offset
from pandas_ta.utils import unsigned_differences, verify_series


def rvi(close, high=None, low=None, length=None, scalar=None, refined=None, thirds=None, mamode=None, drift=None, offset=None, **kwargs):
    """Indicator: Relative Volatility Index (RVI)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 14
    scalar = float(scalar) if scalar and scalar > 0 else 100
    refined = False if refined is None else refined
    thirds = False if thirds is None else thirds
    mamode = mamode if isinstance(mamode, str) else "ema"
    close = verify_series(close, length)
    drift = get_drift(drift)
    offset = get_offset(offset)

    if close is None: return

    if refined or thirds:
        high = verify_series(high)
        low = verify_series(low)

    # Calculate Result
    def _rvi(source, length, scalar, mode, drift):
        """RVI"""
        std = stdev(source, length)
        pos, neg = unsigned_differences(source, amount=drift)

        pos_std = pos * std
        neg_std = neg * std

        pos_avg = ma(mode, pos_std, length=length)
        neg_avg = ma(mode, neg_std, length=length)

        result = scalar * pos_avg
        result /= pos_avg + neg_avg
        return result

    _mode = ""
    if refined:
        high_rvi = _rvi(high, length, scalar, mamode, drift)
        low_rvi = _rvi(low, length, scalar, mamode, drift)
        rvi = 0.5 * (high_rvi + low_rvi)
        _mode = "r"
    elif thirds:
        high_rvi = _rvi(high, length, scalar, mamode, drift)
        low_rvi = _rvi(low, length, scalar, mamode, drift)
        close_rvi = _rvi(close, length, scalar, mamode, drift)
        rvi = (high_rvi + low_rvi + close_rvi) / 3.0
        _mode = "t"
    else:
        rvi = _rvi(close, length, scalar, mamode, drift)

    # Offset
    if offset != 0:
        rvi = rvi.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        rvi.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        rvi.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    rvi.name = f"RVI{_mode}_{length}"
    rvi.category = "volatility"

    return rvi


rvi.__doc__ = \
"""Relative Volatility Index (RVI)

The Relative Volatility Index (RVI) was created in 1993 and revised in 1995.
Instead of adding up price changes like RSI based on price direction, the RVI
adds up standard deviations based on price direction.

Sources:
    https://www.tradingview.com/wiki/Keltner_Channels_(KC)

Calculation:
    Default Inputs:
        length=14, scalar=100, refined=None, thirds=None
    EMA = Exponential Moving Average
    STDEV = Standard Deviation

    UP = STDEV(src, length) IF src.diff() > 0 ELSE 0
    DOWN = STDEV(src, length) IF src.diff() <= 0 ELSE 0

    UPSUM = EMA(UP, length)
    DOWNSUM = EMA(DOWN, length

    RVI = scalar * (UPSUM / (UPSUM + DOWNSUM))

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): The short period. Default: 14
    scalar (float): A positive float to scale the bands. Default: 100
    refined (bool): Use 'refined' calculation which is the average of
        RVI(high) and RVI(low) instead of RVI(close). Default: False
    thirds (bool): Average of high, low and close. Default: False
    mamode (str): See ```help(ta.ma)```. Default: 'ema'
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: lower, basis, upper columns.
"""
