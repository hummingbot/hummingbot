# -*- coding: utf-8 -*-
from pandas_ta.overlap import ema, sma
from pandas_ta.volatility import atr
from pandas_ta.utils import get_offset, verify_series


def pgo(high, low, close, length=None, offset=None, **kwargs):
    """Indicator: Pretty Good Oscillator (PGO)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 14
    high = verify_series(high, length)
    low = verify_series(low, length)
    close = verify_series(close, length)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    # Calculate Result
    pgo = close - sma(close, length)
    pgo /= ema(atr(high, low, close, length), length)

    # Offset
    if offset != 0:
        pgo = pgo.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        pgo.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        pgo.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    pgo.name = f"PGO_{length}"
    pgo.category = "momentum"

    return pgo


pgo.__doc__ = \
"""Pretty Good Oscillator (PGO)

The Pretty Good Oscillator indicator was created by Mark Johnson to measure the distance of the current close from its N-day Simple Moving Average, expressed in terms of an average true range over a similar period. Johnson's approach was to
use it as a breakout system for longer term trades. Long if greater than 3.0 and
short if less than -3.0.

Sources:
    https://library.tradingtechnologies.com/trade/chrt-ti-pretty-good-oscillator.html

Calculation:
    Default Inputs:
        length=14
    ATR = Average True Range
    SMA = Simple Moving Average
    EMA = Exponential Moving Average

    PGO = (close - SMA(close, length)) / EMA(ATR(high, low, close, length), length)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 14
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
