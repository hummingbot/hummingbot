# -*- coding: utf-8 -*-
from pandas import DataFrame
from .true_range import true_range
from pandas_ta.overlap import ma
from pandas_ta.utils import get_offset, high_low_range, verify_series


def kc(high, low, close, length=None, scalar=None, mamode=None, offset=None, **kwargs):
    """Indicator: Keltner Channels (KC)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 20
    scalar = float(scalar) if scalar and scalar > 0 else 2
    mamode = mamode if isinstance(mamode, str) else "ema"
    high = verify_series(high, length)
    low = verify_series(low, length)
    close = verify_series(close, length)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    # Calculate Result
    use_tr = kwargs.pop("tr", True)
    if use_tr:
        range_ = true_range(high, low, close)
    else:
        range_ = high_low_range(high, low)

    basis = ma(mamode, close, length=length)
    band = ma(mamode, range_, length=length)

    lower = basis - scalar * band
    upper = basis + scalar * band

    # Offset
    if offset != 0:
        lower = lower.shift(offset)
        basis = basis.shift(offset)
        upper = upper.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        lower.fillna(kwargs["fillna"], inplace=True)
        basis.fillna(kwargs["fillna"], inplace=True)
        upper.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        lower.fillna(method=kwargs["fill_method"], inplace=True)
        basis.fillna(method=kwargs["fill_method"], inplace=True)
        upper.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = f"{mamode.lower()[0] if len(mamode) else ''}_{length}_{scalar}"
    lower.name = f"KCL{_props}"
    basis.name = f"KCB{_props}"
    upper.name = f"KCU{_props}"
    basis.category = upper.category = lower.category = "volatility"

    # Prepare DataFrame to return
    data = {lower.name: lower, basis.name: basis, upper.name: upper}
    kcdf = DataFrame(data)
    kcdf.name = f"KC{_props}"
    kcdf.category = basis.category

    return kcdf


kc.__doc__ = \
"""Keltner Channels (KC)

A popular volatility indicator similar to Bollinger Bands and
Donchian Channels.

Sources:
    https://www.tradingview.com/wiki/Keltner_Channels_(KC)

Calculation:
    Default Inputs:
        length=20, scalar=2, mamode=None, tr=True
    TR = True Range
    SMA = Simple Moving Average
    EMA = Exponential Moving Average

    if tr:
        RANGE = TR(high, low, close)
    else:
        RANGE = high - low

    if mamode == "ema":
        BASIS = sma(close, length)
        BAND = sma(RANGE, length)
    elif mamode == "sma":
        BASIS = sma(close, length)
        BAND = sma(RANGE, length)

    LOWER = BASIS - scalar * BAND
    UPPER = BASIS + scalar * BAND

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): The short period.  Default: 20
    scalar (float): A positive float to scale the bands. Default: 2
    mamode (str): See ```help(ta.ma)```. Default: 'ema'
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    tr (bool): When True, it uses True Range for calculation. When False, use a
        high - low as it's range calculation. Default: True
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: lower, basis, upper columns.
"""
