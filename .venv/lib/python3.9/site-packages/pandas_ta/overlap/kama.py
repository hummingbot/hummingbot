# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas import Series
from pandas_ta.utils import get_drift, get_offset, non_zero_range, verify_series


def kama(close, length=None, fast=None, slow=None, drift=None, offset=None, **kwargs):
    """Indicator: Kaufman's Adaptive Moving Average (KAMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    fast = int(fast) if fast and fast > 0 else 2
    slow = int(slow) if slow and slow > 0 else 30
    close = verify_series(close, max(fast, slow, length))
    drift = get_drift(drift)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    def weight(length: int) -> float:
        return 2 / (length + 1)

    fr = weight(fast)
    sr = weight(slow)

    abs_diff = non_zero_range(close, close.shift(length)).abs()
    peer_diff = non_zero_range(close, close.shift(drift)).abs()
    peer_diff_sum = peer_diff.rolling(length).sum()
    er = abs_diff / peer_diff_sum
    x = er * (fr - sr) + sr
    sc = x * x

    m = close.size
    result = [npNaN for _ in range(0, length - 1)] + [0]
    for i in range(length, m):
        result.append(sc.iloc[i] * close.iloc[i] + (1 - sc.iloc[i]) * result[i - 1])

    kama = Series(result, index=close.index)

    # Offset
    if offset != 0:
        kama = kama.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        kama.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        kama.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    kama.name = f"KAMA_{length}_{fast}_{slow}"
    kama.category = "overlap"

    return kama


kama.__doc__ = \
"""Kaufman's Adaptive Moving Average (KAMA)

Developed by Perry Kaufman, Kaufman's Adaptive Moving Average (KAMA) is a moving average
designed to account for market noise or volatility. KAMA will closely follow prices when
the price swings are relatively small and the noise is low. KAMA will adjust when the
price swings widen and follow prices from a greater distance. This trend-following indicator
can be used to identify the overall trend, time turning points and filter price movements.

Sources:
    https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:kaufman_s_adaptive_moving_average
    https://www.tradingview.com/script/wZGOIz9r-REPOST-Indicators-3-Different-Adaptive-Moving-Averages/

Calculation:
    Default Inputs:
        length=10

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 10
    fast (int): Fast MA period. Default: 2
    slow (int): Slow MA period. Default: 30
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
