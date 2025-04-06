# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.overlap import rma
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def kdj(high=None, low=None, close=None, length=None, signal=None, offset=None, **kwargs):
    """Indicator: KDJ (KDJ)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 9
    signal = int(signal) if signal and signal > 0 else 3
    _length = max(length, signal)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    # Calculate Result
    highest_high = high.rolling(length).max()
    lowest_low = low.rolling(length).min()

    fastk = 100 * (close - lowest_low) / non_zero_range(highest_high, lowest_low)

    k = rma(fastk, length=signal)
    d = rma(k, length=signal)
    j = 3 * k - 2 * d

    # Offset
    if offset != 0:
        k = k.shift(offset)
        d = d.shift(offset)
        j = j.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        k.fillna(kwargs["fillna"], inplace=True)
        d.fillna(kwargs["fillna"], inplace=True)
        j.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        k.fillna(method=kwargs["fill_method"], inplace=True)
        d.fillna(method=kwargs["fill_method"], inplace=True)
        j.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _params = f"_{length}_{signal}"
    k.name = f"K{_params}"
    d.name = f"D{_params}"
    j.name = f"J{_params}"
    k.category = d.category = j.category = "momentum"

    # Prepare DataFrame to return
    kdjdf = DataFrame({k.name: k, d.name: d, j.name: j})
    kdjdf.name = f"KDJ{_params}"
    kdjdf.category = "momentum"

    return kdjdf


kdj.__doc__ = \
"""KDJ (KDJ)

The KDJ indicator is actually a derived form of the Slow
Stochastic with the only difference being an extra line
called the J line. The J line represents the divergence
of the %D value from the %K. The value of J can go
beyond [0, 100] for %K and %D lines on the chart.

Sources:
    https://www.prorealcode.com/prorealtime-indicators/kdj/
    https://docs.anychart.com/Stock_Charts/Technical_Indicators/Mathematical_Description#kdj

Calculation:
    Default Inputs:
        length=9, signal=3
    LL = low for last 9 periods
    HH = high for last 9 periods

    FAST_K = 100 * (close - LL) / (HH - LL)

    K = RMA(FAST_K, signal)
    D = RMA(K, signal)
    J = 3K - 2D

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): Default: 9
    signal (int): Default: 3
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
