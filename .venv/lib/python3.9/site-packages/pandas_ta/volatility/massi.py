# -*- coding: utf-8 -*-
from pandas_ta.overlap import ema
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def massi(high, low, fast=None, slow=None, offset=None, **kwargs):
    """Indicator: Mass Index (MASSI)"""
    # Validate arguments
    fast = int(fast) if fast and fast > 0 else 9
    slow = int(slow) if slow and slow > 0 else 25
    if slow < fast:
        fast, slow = slow, fast
    _length = max(fast, slow)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    offset = get_offset(offset)
    if "length" in kwargs: kwargs.pop("length")

    if high is None or low is None: return

    # Calculate Result
    high_low_range = non_zero_range(high, low)
    hl_ema1 = ema(close=high_low_range, length=fast, **kwargs)
    hl_ema2 = ema(close=hl_ema1, length=fast, **kwargs)

    hl_ratio = hl_ema1 / hl_ema2
    massi = hl_ratio.rolling(slow, min_periods=slow).sum()

    # Offset
    if offset != 0:
        massi = massi.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        massi.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        massi.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    massi.name = f"MASSI_{fast}_{slow}"
    massi.category = "volatility"

    return massi


massi.__doc__ = \
"""Mass Index (MASSI)

The Mass Index is a non-directional volatility indicator that utilitizes the
High-Low Range to identify trend reversals based on range expansions.

Sources:
    https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:mass_index
    mi = sum(ema(high - low, 9) / ema(ema(high - low, 9), 9), length)

Calculation:
    Default Inputs:
        fast: 9, slow: 25
    EMA = Exponential Moving Average
    hl = high - low
    hl_ema1 = EMA(hl, fast)
    hl_ema2 = EMA(hl_ema1, fast)
    hl_ratio = hl_ema1 / hl_ema2
    MASSI = SUM(hl_ratio, slow)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    fast (int): The short period. Default: 9
    slow (int): The long period. Default: 25
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
