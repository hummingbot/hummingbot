# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.volatility import atr
from pandas_ta.utils import get_offset, verify_series


def cksp(high, low, close, p=None, x=None, q=None, tvmode=None, offset=None, **kwargs):
    """Indicator: Chande Kroll Stop (CKSP)"""
    # Validate Arguments
    # TV defaults=(10,1,9), book defaults = (10,3,20)
    p = int(p) if p and p > 0 else 10
    x = float(x) if x and x > 0 else 1 if tvmode is True else 3
    q = int(q) if q and q > 0 else 9 if tvmode is True else 20
    _length = max(p, q, x)

    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    if high is None or low is None or close is None: return

    offset = get_offset(offset)
    tvmode = tvmode if isinstance(tvmode, bool) else True
    mamode = "rma" if tvmode is True else "sma"

    # Calculate Result
    atr_ = atr(high=high, low=low, close=close, length=p, mamode=mamode)

    long_stop_ = high.rolling(p).max() - x * atr_
    long_stop = long_stop_.rolling(q).max()

    short_stop_ = low.rolling(p).min() + x * atr_
    short_stop = short_stop_.rolling(q).min()

    # Offset
    if offset != 0:
        long_stop = long_stop.shift(offset)
        short_stop = short_stop.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        long_stop.fillna(kwargs["fillna"], inplace=True)
        short_stop.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        long_stop.fillna(method=kwargs["fill_method"], inplace=True)
        short_stop.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = f"_{p}_{x}_{q}"
    long_stop.name = f"CKSPl{_props}"
    short_stop.name = f"CKSPs{_props}"
    long_stop.category = short_stop.category = "trend"

    # Prepare DataFrame to return
    ckspdf = DataFrame({long_stop.name: long_stop, short_stop.name: short_stop})
    ckspdf.name = f"CKSP{_props}"
    ckspdf.category = long_stop.category

    return ckspdf


cksp.__doc__ = \
"""Chande Kroll Stop (CKSP)

The Tushar Chande and Stanley Kroll in their book
“The New Technical Trader”. It is a trend-following indicator,
identifying your stop by calculating the average true range of
the recent market volatility. The indicator defaults to the implementation
found on tradingview but it provides the original book implementation as well,
which differs by the default periods and moving average mode. While the trading
view implementation uses the Welles Wilder moving average, the book uses a
simple moving average.

Sources:
    https://www.multicharts.com/discussion/viewtopic.php?t=48914
    "The New Technical Trader", Wikey 1st ed. ISBN 9780471597803, page 95

Calculation:
    Default Inputs:
        p=10, x=1, q=9, tvmode=True
    ATR = Average True Range

    LS0 = high.rolling(p).max() - x * ATR(length=p)
    LS = LS0.rolling(q).max()

    SS0 = high.rolling(p).min() + x * ATR(length=p)
    SS = SS0.rolling(q).min()

Args:
    close (pd.Series): Series of 'close's
    p (int): ATR and first stop period. Default: 10 in both modes
    x (float): ATR scalar. Default: 1 in TV mode, 3 otherwise
    q (int): Second stop period. Default: 9 in TV mode, 20 otherwise
    tvmode (bool): Trading View or book implementation mode. Default: True
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: long and short columns.
"""
