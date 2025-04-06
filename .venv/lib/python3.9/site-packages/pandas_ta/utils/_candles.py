# -*- coding: utf-8 -*-
from pandas import Series

from ._core import non_zero_range


def candle_color(open_: Series, close: Series) -> Series:
    color = close.copy().astype(int)
    color[close >= open_] = 1
    color[close < open_] = -1
    return color


def high_low_range(high: Series, low: Series) -> Series:
    return non_zero_range(high, low)


def real_body(open_: Series, close: Series) -> Series:
    return non_zero_range(close, open_)
