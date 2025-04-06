# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta import Imports
from pandas_ta.utils import get_offset, verify_series
from pandas_ta.utils import recent_maximum_index, recent_minimum_index


def aroon(high, low, length=None, scalar=None, talib=None, offset=None, **kwargs):
    """Indicator: Aroon & Aroon Oscillator"""
    # Validate Arguments
    length = length if length and length > 0 else 14
    scalar = float(scalar) if scalar else 100
    high = verify_series(high, length)
    low = verify_series(low, length)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if high is None or low is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import AROON, AROONOSC
        aroon_down, aroon_up = AROON(high, low, length)
        aroon_osc = AROONOSC(high, low, length)
    else:
        periods_from_hh = high.rolling(length + 1).apply(recent_maximum_index, raw=True)
        periods_from_ll = low.rolling(length + 1).apply(recent_minimum_index, raw=True)

        aroon_up = aroon_down = scalar
        aroon_up *= 1 - (periods_from_hh / length)
        aroon_down *= 1 - (periods_from_ll / length)
        aroon_osc = aroon_up - aroon_down

    # Handle fills
    if "fillna" in kwargs:
        aroon_up.fillna(kwargs["fillna"], inplace=True)
        aroon_down.fillna(kwargs["fillna"], inplace=True)
        aroon_osc.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        aroon_up.fillna(method=kwargs["fill_method"], inplace=True)
        aroon_down.fillna(method=kwargs["fill_method"], inplace=True)
        aroon_osc.fillna(method=kwargs["fill_method"], inplace=True)

    # Offset
    if offset != 0:
        aroon_up = aroon_up.shift(offset)
        aroon_down = aroon_down.shift(offset)
        aroon_osc = aroon_osc.shift(offset)

    # Name and Categorize it
    aroon_up.name = f"AROONU_{length}"
    aroon_down.name = f"AROOND_{length}"
    aroon_osc.name = f"AROONOSC_{length}"

    aroon_down.category = aroon_up.category = aroon_osc.category = "trend"

    # Prepare DataFrame to return
    data = {
        aroon_down.name: aroon_down,
        aroon_up.name: aroon_up,
        aroon_osc.name: aroon_osc,
    }
    aroondf = DataFrame(data)
    aroondf.name = f"AROON_{length}"
    aroondf.category = aroon_down.category

    return aroondf


aroon.__doc__ = \
"""Aroon & Aroon Oscillator (AROON)

Aroon attempts to identify if a security is trending and how strong.

Sources:
    https://www.tradingview.com/wiki/Aroon
    https://www.tradingtechnologies.com/help/x-study/technical-indicator-definitions/aroon-ar/

Calculation:
    Default Inputs:
        length=1, scalar=100

    recent_maximum_index(x): return int(np.argmax(x[::-1]))
    recent_minimum_index(x): return int(np.argmin(x[::-1]))

    periods_from_hh = high.rolling(length + 1).apply(recent_maximum_index, raw=True)
    AROON_UP = scalar * (1 - (periods_from_hh / length))

    periods_from_ll = low.rolling(length + 1).apply(recent_minimum_index, raw=True)
    AROON_DN = scalar * (1 - (periods_from_ll / length))

    AROON_OSC = AROON_UP - AROON_DN

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 14
    scalar (float): How much to magnify. Default: 100
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: aroon_up, aroon_down, aroon_osc columns.
"""
