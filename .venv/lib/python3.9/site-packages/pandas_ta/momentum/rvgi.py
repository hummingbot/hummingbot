# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.overlap import swma
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def rvgi(open_, high, low, close, length=None, swma_length=None, offset=None, **kwargs):
    """Indicator: Relative Vigor Index (RVGI)"""
    # Validate Arguments
    high_low_range = non_zero_range(high, low)
    close_open_range = non_zero_range(close, open_)
    length = int(length) if length and length > 0 else 14
    swma_length = int(swma_length) if swma_length and swma_length > 0 else 4
    _length = max(length, swma_length)
    open_ = verify_series(open_, _length)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)

    if open_ is None or high is None or low is None or close is None: return

    # Calculate Result
    numerator = swma(close_open_range, length=swma_length).rolling(length).sum()
    denominator = swma(high_low_range, length=swma_length).rolling(length).sum()

    rvgi = numerator / denominator
    signal = swma(rvgi, length=swma_length)

    # Offset
    if offset != 0:
        rvgi = rvgi.shift(offset)
        signal = signal.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        rvgi.fillna(kwargs["fillna"], inplace=True)
        signal.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        rvgi.fillna(method=kwargs["fill_method"], inplace=True)
        signal.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    rvgi.name = f"RVGI_{length}_{swma_length}"
    signal.name = f"RVGIs_{length}_{swma_length}"
    rvgi.category = signal.category = "momentum"

    # Prepare DataFrame to return
    df = DataFrame({rvgi.name: rvgi, signal.name: signal})
    df.name = f"RVGI_{length}_{swma_length}"
    df.category = rvgi.category

    return df


rvgi.__doc__ = \
"""Relative Vigor Index (RVGI)

The Relative Vigor Index attempts to measure the strength of a trend relative to
its closing price to its trading range.  It is based on the belief that it tends
to close higher than they open in uptrends or close lower than they open in
downtrends.

Sources:
    https://www.investopedia.com/terms/r/relative_vigor_index.asp

Calculation:
    Default Inputs:
        length=14, swma_length=4
    SWMA = Symmetrically Weighted Moving Average
    numerator = SUM(SWMA(close - open, swma_length), length)
    denominator = SUM(SWMA(high - low, swma_length), length)
    RVGI = numerator / denominator

Args:
    open_ (pd.Series): Series of 'open's
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 14
    swma_length (int): It's period. Default: 4
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
