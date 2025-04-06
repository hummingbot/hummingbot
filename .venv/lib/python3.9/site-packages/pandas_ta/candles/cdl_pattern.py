# -*- coding: utf-8 -*-
from typing import Sequence, Union
from pandas import Series, DataFrame

from . import cdl_doji, cdl_inside
from pandas_ta.utils import get_offset, verify_series
from pandas_ta import Imports


ALL_PATTERNS = [
    "2crows", "3blackcrows", "3inside", "3linestrike", "3outside", "3starsinsouth",
    "3whitesoldiers", "abandonedbaby", "advanceblock", "belthold", "breakaway",
    "closingmarubozu", "concealbabyswall", "counterattack", "darkcloudcover", "doji",
    "dojistar", "dragonflydoji", "engulfing", "eveningdojistar", "eveningstar",
    "gapsidesidewhite", "gravestonedoji", "hammer", "hangingman", "harami",
    "haramicross", "highwave", "hikkake", "hikkakemod", "homingpigeon",
    "identical3crows", "inneck", "inside", "invertedhammer", "kicking", "kickingbylength",
    "ladderbottom", "longleggeddoji", "longline", "marubozu", "matchinglow", "mathold",
    "morningdojistar", "morningstar", "onneck", "piercing", "rickshawman",
    "risefall3methods", "separatinglines", "shootingstar", "shortline", "spinningtop",
    "stalledpattern", "sticksandwich", "takuri", "tasukigap", "thrusting", "tristar",
    "unique3river", "upsidegap2crows", "xsidegap3methods"
]


def cdl_pattern(open_, high, low, close, name: Union[str, Sequence[str]]="all", scalar=None, offset=None, **kwargs) -> DataFrame:
    """Candle Pattern"""
    # Validate Arguments
    open_ = verify_series(open_)
    high = verify_series(high)
    low = verify_series(low)
    close = verify_series(close)
    offset = get_offset(offset)
    scalar = float(scalar) if scalar else 100

    # Patterns that implemented in pandas-ta
    pta_patterns = {
        "doji": cdl_doji, "inside": cdl_inside,
    }

    if name == "all":
        name = ALL_PATTERNS
    if type(name) is str:
        name = [name]

    if Imports["talib"]:
        import talib.abstract as tala

    result = {}
    for n in name:
        if n not in ALL_PATTERNS:
            print(f"[X] There is no candle pattern named {n} available!")
            continue

        if n in pta_patterns:
            pattern_result = pta_patterns[n](open_, high, low, close, offset=offset, scalar=scalar, **kwargs)
            result[pattern_result.name] = pattern_result
        else:
            if not Imports["talib"]:
                print(f"[X] Please install TA-Lib to use {n}. (pip install TA-Lib)")
                continue

            pattern_func = tala.Function(f"CDL{n.upper()}")
            pattern_result = Series(pattern_func(open_, high, low, close, **kwargs) / 100 * scalar)
            pattern_result.index = close.index

            # Offset
            if offset != 0:
                pattern_result = pattern_result.shift(offset)

            # Handle fills
            if "fillna" in kwargs:
                pattern_result.fillna(kwargs["fillna"], inplace=True)
            if "fill_method" in kwargs:
                pattern_result.fillna(method=kwargs["fill_method"], inplace=True)

            result[f"CDL_{n.upper()}"] = pattern_result

    if len(result) == 0: return

    # Prepare DataFrame to return
    df = DataFrame(result)
    df.name = "CDL_PATTERN"
    df.category = "candles"
    return df


cdl_pattern.__doc__ = \
"""Candle Pattern

A wrapper around all candle patterns.

Examples:

Get all candle patterns (This is the default behaviour)
>>> df = df.ta.cdl_pattern(name="all")
Or
>>> df.ta.cdl("all", append=True) # = df.ta.cdl_pattern("all", append=True)

Get only one pattern
>>> df = df.ta.cdl_pattern(name="doji")
Or
>>> df.ta.cdl("doji", append=True)

Get some patterns
>>> df = df.ta.cdl_pattern(name=["doji", "inside"])
Or
>>> df.ta.cdl(["doji", "inside"], append=True)

Args:
    open_ (pd.Series): Series of 'open's
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    name: (Union[str, Sequence[str]]): name of the patterns
    scalar (float): How much to magnify. Default: 100
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: one column for each pattern.
"""

cdl = cdl_pattern