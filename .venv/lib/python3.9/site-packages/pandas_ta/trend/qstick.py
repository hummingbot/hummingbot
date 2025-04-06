# -*- coding: utf-8 -*-
from pandas_ta.overlap import dema, ema, hma, rma, sma
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def qstick(open_, close, length=None, offset=None, **kwargs):
    """Indicator: Q Stick"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    ma = kwargs.pop("ma", "sma")
    open_ = verify_series(open_, length)
    close = verify_series(close, length)
    offset = get_offset(offset)

    if open_ is None or close is None: return

    # Calculate Result
    diff = non_zero_range(close, open_)

    if ma == "dema":
        qstick = dema(diff, length=length, **kwargs)
    elif ma == "ema":
        qstick = ema(diff, length=length, **kwargs)
    elif ma == "hma":
        qstick = hma(diff, length=length)
    elif ma == "rma":
        qstick = rma(diff, length=length)
    else: # "sma"
        qstick = sma(diff, length=length)

    # Offset
    if offset != 0:
        qstick = qstick.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        qstick.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        qstick.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    qstick.name = f"QS_{length}"
    qstick.category = "trend"

    return qstick


qstick.__doc__ = \
"""Q Stick

The Q Stick indicator, developed by Tushar Chande, attempts to quantify and
identify trends in candlestick charts.

Sources:
    https://library.tradingtechnologies.com/trade/chrt-ti-qstick.html

Calculation:
    Default Inputs:
        length=10
    xMA is one of: sma (default), dema, ema, hma, rma
    qstick = xMA(close - open, length)

Args:
    open (pd.Series): Series of 'open's
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 1
    ma (str): The type of moving average to use. Default: None, which is 'sma'
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
