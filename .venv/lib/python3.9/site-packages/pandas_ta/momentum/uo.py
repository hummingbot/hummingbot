# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta import Imports
from pandas_ta.utils import get_drift, get_offset, verify_series


def uo(high, low, close, fast=None, medium=None, slow=None, fast_w=None, medium_w=None, slow_w=None, talib=None, drift=None, offset=None, **kwargs):
    """Indicator: Ultimate Oscillator (UO)"""
    # Validate arguments
    fast = int(fast) if fast and fast > 0 else 7
    fast_w = float(fast_w) if fast_w and fast_w > 0 else 4.0
    medium = int(medium) if medium and medium > 0 else 14
    medium_w = float(medium_w) if medium_w and medium_w > 0 else 2.0
    slow = int(slow) if slow and slow > 0 else 28
    slow_w = float(slow_w) if slow_w and slow_w > 0 else 1.0
    _length = max(fast, medium, slow)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    drift = get_drift(drift)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if high is None or low is None or close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import ULTOSC
        uo = ULTOSC(high, low, close, fast, medium, slow)
    else:
        tdf = DataFrame({
            "high": high,
            "low": low,
            f"close_{drift}": close.shift(drift)
        })
        max_h_or_pc = tdf.loc[:, ["high", f"close_{drift}"]].max(axis=1)
        min_l_or_pc = tdf.loc[:, ["low", f"close_{drift}"]].min(axis=1)
        del tdf

        bp = close - min_l_or_pc
        tr = max_h_or_pc - min_l_or_pc

        fast_avg = bp.rolling(fast).sum() / tr.rolling(fast).sum()
        medium_avg = bp.rolling(medium).sum() / tr.rolling(medium).sum()
        slow_avg = bp.rolling(slow).sum() / tr.rolling(slow).sum()

        total_weight = fast_w + medium_w + slow_w
        weights = (fast_w * fast_avg) + (medium_w * medium_avg) + (slow_w * slow_avg)
        uo = 100 * weights / total_weight

    # Offset
    if offset != 0:
        uo = uo.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        uo.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        uo.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    uo.name = f"UO_{fast}_{medium}_{slow}"
    uo.category = "momentum"

    return uo


uo.__doc__ = \
"""Ultimate Oscillator (UO)

The Ultimate Oscillator is a momentum indicator over three different
periods.  It attempts to correct false divergence trading signals.

Sources:
    https://www.tradingview.com/wiki/Ultimate_Oscillator_(UO)

Calculation:
    Default Inputs:
        fast=7, medium=14, slow=28,
        fast_w=4.0, medium_w=2.0, slow_w=1.0, drift=1
    min_low_or_pc  = close.shift(drift).combine(low, min)
    max_high_or_pc = close.shift(drift).combine(high, max)

    bp = buying pressure = close - min_low_or_pc
    tr = true range = max_high_or_pc - min_low_or_pc

    fast_avg = SUM(bp, fast) / SUM(tr, fast)
    medium_avg = SUM(bp, medium) / SUM(tr, medium)
    slow_avg = SUM(bp, slow) / SUM(tr, slow)

    total_weight = fast_w + medium_w + slow_w
    weights = (fast_w * fast_avg) + (medium_w * medium_avg) + (slow_w * slow_avg)
    UO = 100 * weights / total_weight

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    fast (int): The Fast %K period. Default: 7
    medium (int): The Slow %K period. Default: 14
    slow (int): The Slow %D period. Default: 28
    fast_w (float): The Fast %K period. Default: 4.0
    medium_w (float): The Slow %K period. Default: 2.0
    slow_w (float): The Slow %D period. Default: 1.0
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
