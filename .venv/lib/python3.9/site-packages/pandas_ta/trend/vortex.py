# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.volatility import true_range
from pandas_ta.utils import get_drift, get_offset, verify_series


def vortex(high, low, close, length=None, drift=None, offset=None, **kwargs):
    """Indicator: Vortex"""
    # Validate arguments
    length = length if length and length > 0 else 14
    min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    _length = max(length, min_periods)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    drift = get_drift(drift)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    # Calculate Result
    tr = true_range(high=high, low=low, close=close)
    tr_sum = tr.rolling(length, min_periods=min_periods).sum()

    vmp = (high - low.shift(drift)).abs()
    vmm = (low - high.shift(drift)).abs()

    vip = vmp.rolling(length, min_periods=min_periods).sum() / tr_sum
    vim = vmm.rolling(length, min_periods=min_periods).sum() / tr_sum

    # Offset
    if offset != 0:
        vip = vip.shift(offset)
        vim = vim.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        vip.fillna(kwargs["fillna"], inplace=True)
        vim.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        vip.fillna(method=kwargs["fill_method"], inplace=True)
        vim.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    vip.name = f"VTXP_{length}"
    vim.name = f"VTXM_{length}"
    vip.category = vim.category = "trend"

    # Prepare DataFrame to return
    data = {vip.name: vip, vim.name: vim}
    vtxdf = DataFrame(data)
    vtxdf.name = f"VTX_{length}"
    vtxdf.category = "trend"

    return vtxdf


vortex.__doc__ = \
"""Vortex

Two oscillators that capture positive and negative trend movement.

Sources:
    https://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vortex_indicator

Calculation:
    Default Inputs:
        length=14, drift=1
    TR = True Range
    SMA = Simple Moving Average
    tr = TR(high, low, close)
    tr_sum = tr.rolling(length).sum()

    vmp = (high - low.shift(drift)).abs()
    vmn = (low - high.shift(drift)).abs()

    VIP = vmp.rolling(length).sum() / tr_sum
    VIM = vmn.rolling(length).sum() / tr_sum

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): ROC 1 period. Default: 14
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: vip and vim columns
"""
