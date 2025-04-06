# -*- coding: utf-8 -*-
from numpy import log as nplog
from numpy import seterr
from pandas import DataFrame
from pandas_ta.utils import get_offset, verify_series


def drawdown(close, offset=None, **kwargs) -> DataFrame:
    """Indicator: Drawdown (DD)"""
    # Validate Arguments
    close = verify_series(close)
    offset = get_offset(offset)

    # Calculate Result
    max_close = close.cummax()
    dd = max_close - close
    dd_pct = 1 - (close / max_close)

    _np_err = seterr()
    seterr(divide="ignore", invalid="ignore")
    dd_log = nplog(max_close) - nplog(close)
    seterr(divide=_np_err["divide"], invalid=_np_err["invalid"])

    # Offset
    if offset != 0:
        dd = dd.shift(offset)
        dd_pct = dd_pct.shift(offset)
        dd_log = dd_log.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        dd.fillna(kwargs["fillna"], inplace=True)
        dd_pct.fillna(kwargs["fillna"], inplace=True)
        dd_log.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        dd.fillna(method=kwargs["fill_method"], inplace=True)
        dd_pct.fillna(method=kwargs["fill_method"], inplace=True)
        dd_log.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    dd.name = "DD"
    dd_pct.name = f"{dd.name}_PCT"
    dd_log.name = f"{dd.name}_LOG"
    dd.category = dd_pct.category = dd_log.category = "performance"

    # Prepare DataFrame to return
    data = {dd.name: dd, dd_pct.name: dd_pct, dd_log.name: dd_log}
    df = DataFrame(data)
    df.name = dd.name
    df.category = dd.category

    return df



drawdown.__doc__ = \
"""Drawdown (DD)

Drawdown is a peak-to-trough decline during a specific period for an investment,
trading account, or fund. It is usually quoted as the percentage between the
peak and the subsequent trough.

Sources:
    https://www.investopedia.com/terms/d/drawdown.asp

Calculation:
    PEAKDD = close.cummax()
    DD = PEAKDD - close
    DD% = 1 - (close / PEAKDD)
    DDlog = log(PEAKDD / close)

Args:
    close (pd.Series): Series of 'close's.
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: drawdown, drawdown percent, drawdown log columns
"""
