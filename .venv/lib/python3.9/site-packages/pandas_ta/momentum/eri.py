# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.overlap import ema
from pandas_ta.utils import get_offset, verify_series


def eri(high, low, close, length=None, offset=None, **kwargs):
    """Indicator: Elder Ray Index (ERI)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 13
    high = verify_series(high, length)
    low = verify_series(low, length)
    close = verify_series(close, length)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    # Calculate Result
    ema_ = ema(close, length)
    bull = high - ema_
    bear = low - ema_

    # Offset
    if offset != 0:
        bull = bull.shift(offset)
        bear = bear.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        bull.fillna(kwargs["fillna"], inplace=True)
        bear.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        bull.fillna(method=kwargs["fill_method"], inplace=True)
        bear.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    bull.name = f"BULLP_{length}"
    bear.name = f"BEARP_{length}"
    bull.category = bear.category = "momentum"

    # Prepare DataFrame to return
    data = {bull.name: bull, bear.name: bear}
    df = DataFrame(data)
    df.name = f"ERI_{length}"
    df.category = bull.category

    return df


eri.__doc__ = \
"""Elder Ray Index (ERI)

Elder's Bulls Ray Index contains his Bull and Bear Powers. Which are useful ways
to look at the price and see the strength behind the market. Bull Power
measures the capability of buyers in the market, to lift prices above an average
consensus of value.

Bears Power measures the capability of sellers, to drag prices below an average
consensus of value. Using them in tandem with a measure of trend allows you to
identify favourable entry points. We hope you've found this to be a useful
discussion of the Bulls and Bears Power indicators.

Sources:
    https://admiralmarkets.com/education/articles/forex-indicators/bears-and-bulls-power-indicator

Calculation:
    Default Inputs:
        length=13
    EMA = Exponential Moving Average

    BULLPOWER = high - EMA(close, length)
    BEARPOWER = low - EMA(close, length)

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
    pd.DataFrame: bull power and bear power columns.
"""
