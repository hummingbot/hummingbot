# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.statistics import zscore
from pandas_ta.utils import get_offset, verify_series


def cdl_z(open_, high, low, close, length=None, full=None, ddof=None, offset=None, **kwargs):
    """Candle Type: Z Score"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 30
    ddof = int(ddof) if ddof and ddof >= 0 and ddof < length else 1
    open_ = verify_series(open_, length)
    high = verify_series(high, length)
    low = verify_series(low, length)
    close = verify_series(close, length)
    offset = get_offset(offset)
    full = bool(full) if full is not None and full else False

    if open_ is None or high is None or low is None or close is None: return

    # Calculate Result
    if full:
        length = close.size

    z_open = zscore(open_, length=length, ddof=ddof)
    z_high = zscore(high, length=length, ddof=ddof)
    z_low = zscore(low, length=length, ddof=ddof)
    z_close = zscore(close, length=length, ddof=ddof)

    _full = "a" if full else ""
    _props = _full if full else f"_{length}_{ddof}"
    df = DataFrame({
        f"open_Z{_props}": z_open,
        f"high_Z{_props}": z_high,
        f"low_Z{_props}": z_low,
        f"close_Z{_props}": z_close,
    })

    if full:
        df.fillna(method="backfill", axis=0, inplace=True)

    # Offset
    if offset != 0:
        df = df.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        df.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        df.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    df.name = f"CDL_Z{_props}"
    df.category = "candles"

    return df


cdl_z.__doc__ = \
"""Candle Type: Z

Normalizes OHLC Candles with a rolling Z Score.

Source: Kevin Johnson

Calculation:
    Default values:
        length=30, full=False, ddof=1
    Z = ZSCORE

    open  = Z( open, length, ddof)
    high  = Z( high, length, ddof)
    low   = Z(  low, length, ddof)
    close = Z(close, length, ddof)

Args:
    open_ (pd.Series): Series of 'open's
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): The period. Default: 10

Kwargs:
    naive (bool, optional): If True, prefills potential Doji less than
        the length if less than a percentage of it's high-low range.
        Default: False
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: CDL_DOJI column.
"""
