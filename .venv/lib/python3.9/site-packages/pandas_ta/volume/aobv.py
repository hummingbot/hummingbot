# -*- coding: utf-8 -*-
from pandas import DataFrame
from .obv import obv
from pandas_ta.overlap import ma
from pandas_ta.trend import long_run, short_run
from pandas_ta.utils import get_offset, verify_series


def aobv(close, volume, fast=None, slow=None, max_lookback=None, min_lookback=None, mamode=None, offset=None, **kwargs):
    """Indicator: Archer On Balance Volume (AOBV)"""
    # Validate arguments
    fast = int(fast) if fast and fast > 0 else 4
    slow = int(slow) if slow and slow > 0 else 12
    max_lookback = int(max_lookback) if max_lookback and max_lookback > 0 else 2
    min_lookback = int(min_lookback) if min_lookback and min_lookback > 0 else 2
    if slow < fast:
        fast, slow = slow, fast
    mamode = mamode if isinstance(mamode, str) else "ema"
    _length = max(fast, slow, max_lookback, min_lookback)
    close = verify_series(close, _length)
    volume = verify_series(volume, _length)
    offset = get_offset(offset)
    if "length" in kwargs: kwargs.pop("length")
    run_length = kwargs.pop("run_length", 2)

    if close is None or volume is None: return

    # Calculate Result
    obv_ = obv(close=close, volume=volume, **kwargs)
    maf = ma(mamode, obv_, length=fast, **kwargs)
    mas = ma(mamode, obv_, length=slow, **kwargs)

    # When MAs are long and short
    obv_long = long_run(maf, mas, length=run_length)
    obv_short = short_run(maf, mas, length=run_length)

    # Offset
    if offset != 0:
        obv_ = obv_.shift(offset)
        maf = maf.shift(offset)
        mas = mas.shift(offset)
        obv_long = obv_long.shift(offset)
        obv_short = obv_short.shift(offset)

    # # Handle fills
    if "fillna" in kwargs:
        obv_.fillna(kwargs["fillna"], inplace=True)
        maf.fillna(kwargs["fillna"], inplace=True)
        mas.fillna(kwargs["fillna"], inplace=True)
        obv_long.fillna(kwargs["fillna"], inplace=True)
        obv_short.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        obv_.fillna(method=kwargs["fill_method"], inplace=True)
        maf.fillna(method=kwargs["fill_method"], inplace=True)
        mas.fillna(method=kwargs["fill_method"], inplace=True)
        obv_long.fillna(method=kwargs["fill_method"], inplace=True)
        obv_short.fillna(method=kwargs["fill_method"], inplace=True)

    # Prepare DataFrame to return
    _mode = mamode.lower()[0] if len(mamode) else ""
    data = {
        obv_.name: obv_,
        f"OBV_min_{min_lookback}": obv_.rolling(min_lookback).min(),
        f"OBV_max_{max_lookback}": obv_.rolling(max_lookback).max(),
        f"OBV{_mode}_{fast}": maf,
        f"OBV{_mode}_{slow}": mas,
        f"AOBV_LR_{run_length}": obv_long,
        f"AOBV_SR_{run_length}": obv_short,
    }
    aobvdf = DataFrame(data)

    # Name and Categorize it
    aobvdf.name = f"AOBV{_mode}_{fast}_{slow}_{min_lookback}_{max_lookback}_{run_length}"
    aobvdf.category = "volume"

    return aobvdf
