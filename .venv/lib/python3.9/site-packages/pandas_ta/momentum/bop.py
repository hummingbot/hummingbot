# -*- coding: utf-8 -*-
from pandas_ta import Imports
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def bop(open_, high, low, close, scalar=None, talib=None, offset=None, **kwargs):
    """Indicator: Balance of Power (BOP)"""
    # Validate Arguments
    open_ = verify_series(open_)
    high = verify_series(high)
    low = verify_series(low)
    close = verify_series(close)
    scalar = float(scalar) if scalar else 1
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import BOP
        bop = BOP(open_, high, low, close)
    else:
        high_low_range = non_zero_range(high, low)
        close_open_range = non_zero_range(close, open_)
        bop = scalar * close_open_range / high_low_range

    # Offset
    if offset != 0:
        bop = bop.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        bop.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        bop.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    bop.name = f"BOP"
    bop.category = "momentum"

    return bop


bop.__doc__ = \
"""Balance of Power (BOP)

Balance of Power measure the market strength of buyers against sellers.

Sources:
    http://www.worden.com/TeleChartHelp/Content/Indicators/Balance_of_Power.htm

Calculation:
    BOP = scalar * (close - open) / (high - low)

Args:
    open (pd.Series): Series of 'open's
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    scalar (float): How much to magnify. Default: 1
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
