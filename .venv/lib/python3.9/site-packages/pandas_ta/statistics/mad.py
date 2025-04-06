# -*- coding: utf-8 -*-
from numpy import fabs as npfabs
from pandas_ta.utils import get_offset, verify_series


def mad(close, length=None, offset=None, **kwargs):
    """Indicator: Mean Absolute Deviation"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 30
    min_periods = int(kwargs["min_periods"]) if "min_periods" in kwargs and kwargs["min_periods"] is not None else length
    close = verify_series(close, max(length, min_periods))
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    def mad_(series):
        """Mean Absolute Deviation"""
        return npfabs(series - series.mean()).mean()

    mad = close.rolling(length, min_periods=min_periods).apply(mad_, raw=True)

    # Offset
    if offset != 0:
        mad = mad.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        mad.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        mad.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    mad.name = f"MAD_{length}"
    mad.category = "statistics"

    return mad


mad.__doc__ = \
"""Rolling Mean Absolute Deviation

Sources:

Calculation:
    Default Inputs:
        length=30
    mad = close.rolling(length).mad()

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 30
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
