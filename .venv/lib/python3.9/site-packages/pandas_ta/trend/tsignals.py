# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta.utils import get_drift, get_offset, verify_series


def tsignals(trend, asbool=None, trend_reset=0, trade_offset=None, drift=None, offset=None, **kwargs):
    """Indicator: Trend Signals"""
    # Validate Arguments
    trend = verify_series(trend)
    asbool = bool(asbool) if isinstance(asbool, bool) else False
    trend_reset = int(trend_reset) if trend_reset and isinstance(trend_reset, int) else 0
    if trade_offset !=0:
        trade_offset = int(trade_offset) if trade_offset and isinstance(trade_offset, int) else 0
    drift = get_drift(drift)
    offset = get_offset(offset)

    # Calculate Result
    trends = trend.astype(int)
    trades = trends.diff(drift).shift(trade_offset).fillna(0).astype(int)
    entries = (trades > 0).astype(int)
    exits = (trades < 0).abs().astype(int)

    if asbool:
        trends = trends.astype(bool)
        entries = entries.astype(bool)
        exits = exits.astype(bool)

    data = {
        f"TS_Trends": trends,
        f"TS_Trades": trades,
        f"TS_Entries": entries,
        f"TS_Exits": exits,
    }
    df = DataFrame(data, index=trends.index)

    # Offset
    if offset != 0:
        df = df.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        df.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        df.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    df.name = f"TS"
    df.category = "trend"

    return df


tsignals.__doc__ = \
"""Trend Signals

Given a Trend, Trend Signals returns the Trend, Trades, Entries and Exits as
boolean integers. When 'asbool=True', it returns Trends, Entries and Exits as
boolean values which is helpful when combined with the vectorbt backtesting
package.

A Trend can be a simple as: 'close' > 'moving average' or something more complex
whose values are boolean or integers (0 or 1).

Examples:
ta.tsignals(close > ta.sma(close, 50), asbool=False)
ta.tsignals(ta.ema(close, 8) > ta.ema(close, 21), asbool=True)

Source: Kevin Johnson

Calculation:
    Default Inputs:
        asbool=False, trend_reset=0, trade_offset=0, drift=1

    trades = trends.diff().shift(trade_offset).fillna(0).astype(int)
    entries = (trades > 0).astype(int)
    exits = (trades < 0).abs().astype(int)

Args:
    trend (pd.Series): Series of 'trend's. The trend can be either a boolean or
        integer series of '0's and '1's
    asbool (bool): If True, it converts the Trends, Entries and Exits columns to
        booleans. When boolean, it is also useful for backtesting with
        vectorbt's Portfolio.from_signal(close, entries, exits) Default: False
    trend_reset (value): Value used to identify if a trend has ended. Default: 0
    trade_offset (value): Value used shift the trade entries/exits Use 1 for
        backtesting and 0 for live. Default: 0
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame with columns:
    Trends (trend: 1, no trend: 0), Trades (Enter: 1, Exit: -1, Otherwise: 0),
    Entries (entry: 1, nothing: 0), Exits (exit: 1, nothing: 0)
"""
