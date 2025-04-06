# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas import DataFrame
from .tsignals import tsignals
from pandas_ta.utils._signals import cross_value
from pandas_ta.utils import get_offset, verify_series


def xsignals(signal, xa, xb, above:bool=True, long:bool=True, asbool:bool=None, trend_reset:int=0, trade_offset:int=None, offset:int=None, **kwargs):
    """Indicator: Cross Signals"""
    # Validate Arguments
    signal = verify_series(signal)
    offset = get_offset(offset)

    # Calculate Result
    if above:
        entries = cross_value(signal, xa)
        exits = -cross_value(signal, xb, above=False)
    else:
        entries = cross_value(signal, xa, above=False)
        exits = -cross_value(signal, xb)
    trades = entries + exits

    # Modify trades to fill gaps for trends
    trades.replace({0: npNaN}, inplace=True)
    trades.interpolate(method="pad", inplace=True)
    trades.fillna(0, inplace=True)

    trends = (trades > 0).astype(int)
    if not long:
        trends = 1 - trends

    tskwargs = {
        "asbool":asbool,
        "trade_offset":trade_offset,
        "trend_reset":trend_reset,
        "offset":offset
    }
    df = tsignals(trends, **tskwargs)

    # Offset handled by tsignals
    DataFrame({
        f"XS_LONG": df.TS_Trends,
        f"XS_SHORT": 1 - df.TS_Trends
    })


    # Handle fills
    if "fillna" in kwargs:
        df.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        df.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    df.name = f"XS"
    df.category = "trend"

    return df


xsignals.__doc__ = \
"""Cross Signals (XSIGNALS)

Cross Signals returns Trend Signal (TSIGNALS) results for Signal Crossings. This
is useful for indicators like RSI, ZSCORE, et al where one wants trade Entries
and Exits (and Trends).

Cross Signals has two kinds of modes: above and long.

The first mode 'above', default True, xsignals determines if the signal first
crosses above 'xa' and then below 'xb'. If 'above' is False, xsignals determines
if the signal first crosses below 'xa' and then above 'xb'.

The second mode 'long', default True, passes the long trend result into
tsignals so it can determine the appropriate Entries and Exits. When 'long' is
False, it does the same but for the short side.

Example:
# These are two different outcomes and depends on the indicator and it's
# characteristics. Please check BOTH outcomes BEFORE making an Issue.
rsi = df.ta.rsi()
# Returns tsignal DataFrame when RSI crosses above 20 and then below 80
ta.xsignals(rsi, 20, 80, above=True)
# Returns tsignal DataFrame when RSI crosses below 20 and then above 80
ta.xsignals(rsi, 20, 80, above=False)

Source: Kevin Johnson

Calculation:
    Default Inputs:
        asbool=False, trend_reset=0, trade_offset=0, drift=1

    trades = trends.diff().shift(trade_offset).fillna(0).astype(int)
    entries = (trades > 0).astype(int)
    exits = (trades < 0).abs().astype(int)

Args:
    above (bool): When the signal crosses above 'xa' first and then 'xb'. When
        False, then when the signal crosses below 'xa' first and then 'xb'.
        Default: True
    long (bool): Passes the long trend into tsignals' trend argument. When
        False, it passes the short trend into tsignals trend argument.
        Default: True
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

    # TSIGNAL Passthrough arguments
    asbool (bool): If True, it converts the Trends, Entries and Exits columns to
        booleans. When boolean, it is also useful for backtesting with
        vectorbt's Portfolio.from_signal(close, entries, exits) Default: False
    trend_reset (value): Value used to identify if a trend has ended. Default: 0
    trade_offset (value): Value used shift the trade entries/exits Use 1 for
        backtesting and 0 for live. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame with columns:
    Trends (trend: 1, no trend: 0), Trades (Enter: 1, Exit: -1, Otherwise: 0),
    Entries (entry: 1, nothing: 0), Exits (exit: 1, nothing: 0)
"""
