# -*- coding: utf-8 -*-
from numpy import log as nplog
from numpy import nan as npNaN
from pandas import DataFrame, Series
from pandas_ta.overlap import hl2
from pandas_ta.utils import get_offset, high_low_range, verify_series


def fisher(high, low, length=None, signal=None, offset=None, **kwargs):
    """Indicator: Fisher Transform (FISHT)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 9
    signal = int(signal) if signal and signal > 0 else 1
    _length = max(length, signal)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    offset = get_offset(offset)

    if high is None or low is None: return

    # Calculate Result
    hl2_ = hl2(high, low)
    highest_hl2 = hl2_.rolling(length).max()
    lowest_hl2 = hl2_.rolling(length).min()

    hlr = high_low_range(highest_hl2, lowest_hl2)
    hlr[hlr < 0.001] = 0.001

    position = ((hl2_ - lowest_hl2) / hlr) - 0.5

    v = 0
    m = high.size
    result = [npNaN for _ in range(0, length - 1)] + [0]
    for i in range(length, m):
        v = 0.66 * position.iloc[i] + 0.67 * v
        if v < -0.99: v = -0.999
        if v > 0.99: v = 0.999
        result.append(0.5 * (nplog((1 + v) / (1 - v)) + result[i - 1]))
    fisher = Series(result, index=high.index)
    signalma = fisher.shift(signal)

    # Offset
    if offset != 0:
        fisher = fisher.shift(offset)
        signalma = signalma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        fisher.fillna(kwargs["fillna"], inplace=True)
        signalma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        fisher.fillna(method=kwargs["fill_method"], inplace=True)
        signalma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = f"_{length}_{signal}"
    fisher.name = f"FISHERT{_props}"
    signalma.name = f"FISHERTs{_props}"
    fisher.category = signalma.category = "momentum"

    # Prepare DataFrame to return
    data = {fisher.name: fisher, signalma.name: signalma}
    df = DataFrame(data)
    df.name = f"FISHERT{_props}"
    df.category = fisher.category

    return df


fisher.__doc__ = \
"""Fisher Transform (FISHT)

Attempts to identify significant price reversals by normalizing prices over a
user-specified number of periods. A reversal signal is suggested when the the
two lines cross.

Sources:
    TradingView (Correlation >99%)

Calculation:
    Default Inputs:
        length=9, signal=1
    HL2 = hl2(high, low)
    HHL2 = HL2.rolling(length).max()
    LHL2 = HL2.rolling(length).min()

    HLR = HHL2 - LHL2
    HLR[HLR < 0.001] = 0.001

    position = ((HL2 - LHL2) / HLR) - 0.5

    v = 0
    m = high.size
    FISHER = [npNaN for _ in range(0, length - 1)] + [0]
    for i in range(length, m):
        v = 0.66 * position[i] + 0.67 * v
        if v < -0.99: v = -0.999
        if v >  0.99: v =  0.999
        FISHER.append(0.5 * (nplog((1 + v) / (1 - v)) + FISHER[i - 1]))

    SIGNAL = FISHER.shift(signal)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    length (int): Fisher period. Default: 9
    signal (int): Fisher Signal period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
