# -*- coding: utf-8 -*-
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def cmf(high, low, close, volume, open_=None, length=None, offset=None, **kwargs):
    """Indicator: Chaikin Money Flow (CMF)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 20
    min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    _length = max(length, min_periods)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    volume = verify_series(volume, _length)
    offset = get_offset(offset)

    if high is None or low is None or close is None or volume is None: return

    # Calculate Result
    if open_ is not None:
        open_ = verify_series(open_)
        ad = non_zero_range(close, open_)  # AD with Open
    else:
        ad = 2 * close - (high + low)  # AD with High, Low, Close

    ad *= volume / non_zero_range(high, low)
    cmf = ad.rolling(length, min_periods=min_periods).sum()
    cmf /= volume.rolling(length, min_periods=min_periods).sum()

    # Offset
    if offset != 0:
        cmf = cmf.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        cmf.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        cmf.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    cmf.name = f"CMF_{length}"
    cmf.category = "volume"

    return cmf


cmf.__doc__ = \
"""Chaikin Money Flow (CMF)

Chailin Money Flow measures the amount of money flow volume over a specific
period in conjunction with Accumulation/Distribution.

Sources:
    https://www.tradingview.com/wiki/Chaikin_Money_Flow_(CMF)
    https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:chaikin_money_flow_cmf

Calculation:
    Default Inputs:
        length=20
    if 'open':
        ad = close - open
    else:
        ad = 2 * close - high - low

    hl_range = high - low
    ad = ad * volume / hl_range
    CMF = SUM(ad, length) / SUM(volume, length)

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    volume (pd.Series): Series of 'volume's
    open_ (pd.Series): Series of 'open's. Default: None
    length (int): The short period. Default: 20
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
