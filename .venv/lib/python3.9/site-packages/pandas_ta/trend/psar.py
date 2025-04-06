# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas import DataFrame, Series
from pandas_ta.utils import get_offset, verify_series, zero


def psar(high, low, close=None, af0=None, af=None, max_af=None, offset=None, **kwargs):
    """Indicator: Parabolic Stop and Reverse (PSAR)"""
    # Validate Arguments
    high = verify_series(high)
    low = verify_series(low)
    af = float(af) if af and af > 0 else 0.02
    af0 = float(af0) if af0 and af0 > 0 else af
    max_af = float(max_af) if max_af and max_af > 0 else 0.2
    offset = get_offset(offset)

    def _falling(high, low, drift:int=1):
        """Returns the last -DM value"""
        # Not to be confused with ta.falling()
        up = high - high.shift(drift)
        dn = low.shift(drift) - low
        _dmn = (((dn > up) & (dn > 0)) * dn).apply(zero).iloc[-1]
        return _dmn > 0

    # Falling if the first NaN -DM is positive
    falling = _falling(high.iloc[:2], low.iloc[:2])
    if falling:
        sar = high.iloc[0]
        ep = low.iloc[0]
    else:
        sar = low.iloc[0]
        ep = high.iloc[0]

    if close is not None:
        close = verify_series(close)
        sar = close.iloc[0]

    long = Series(npNaN, index=high.index)
    short = long.copy()
    reversal = Series(0, index=high.index)
    _af = long.copy()
    _af.iloc[0:2] = af0

    # Calculate Result
    m = high.shape[0]
    for row in range(1, m):
        high_ = high.iloc[row]
        low_ = low.iloc[row]

        if falling:
            _sar = sar + af * (ep - sar)
            reverse = high_ > _sar

            if low_ < ep:
                ep = low_
                af = min(af + af0, max_af)

            _sar = max(high.iloc[row - 1], high.iloc[row - 2], _sar)
        else:
            _sar = sar + af * (ep - sar)
            reverse = low_ < _sar

            if high_ > ep:
                ep = high_
                af = min(af + af0, max_af)

            _sar = min(low.iloc[row - 1], low.iloc[row - 2], _sar)

        if reverse:
            _sar = ep
            af = af0
            falling = not falling # Must come before next line
            ep = low_ if falling else high_

        sar = _sar # Update SAR

        # Seperate long/short sar based on falling
        if falling:
            short.iloc[row] = sar
        else:
            long.iloc[row] = sar

        _af.iloc[row] = af
        reversal.iloc[row] = int(reverse)

    # Offset
    if offset != 0:
        _af = _af.shift(offset)
        long = long.shift(offset)
        short = short.shift(offset)
        reversal = reversal.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        _af.fillna(kwargs["fillna"], inplace=True)
        long.fillna(kwargs["fillna"], inplace=True)
        short.fillna(kwargs["fillna"], inplace=True)
        reversal.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        _af.fillna(method=kwargs["fill_method"], inplace=True)
        long.fillna(method=kwargs["fill_method"], inplace=True)
        short.fillna(method=kwargs["fill_method"], inplace=True)
        reversal.fillna(method=kwargs["fill_method"], inplace=True)

    # Prepare DataFrame to return
    _params = f"_{af0}_{max_af}"
    data = {
        f"PSARl{_params}": long,
        f"PSARs{_params}": short,
        f"PSARaf{_params}": _af,
        f"PSARr{_params}": reversal,
    }
    psardf = DataFrame(data)
    psardf.name = f"PSAR{_params}"
    psardf.category = long.category = short.category = "trend"

    return psardf


psar.__doc__ = \
"""Parabolic Stop and Reverse (psar)

Parabolic Stop and Reverse (PSAR) was developed by J. Wells Wilder, that is used
to determine trend direction and it's potential reversals in price. PSAR uses a
trailing stop and reverse method called "SAR," or stop and reverse, to identify
possible entries and exits. It is also known as SAR.

PSAR indicator typically appears on a chart as a series of dots, either above or
below an asset's price, depending on the direction the price is moving. A dot is
placed below the price when it is trending upward, and above the price when it
is trending downward.

Sources:
    https://www.tradingview.com/pine-script-reference/#fun_sar
    https://www.sierrachart.com/index.php?page=doc/StudiesReference.php&ID=66&Name=Parabolic

Calculation:
    Default Inputs:
        af0=0.02, af=0.02, max_af=0.2

    See Source links

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series, optional): Series of 'close's. Optional
    af0 (float): Initial Acceleration Factor. Default: 0.02
    af (float): Acceleration Factor. Default: 0.02
    max_af (float): Maximum Acceleration Factor. Default: 0.2
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: long, short, af, and reversal columns.
"""
