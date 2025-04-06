# -*- coding: utf-8 -*-
from .decreasing import decreasing
from .increasing import increasing
from pandas_ta.utils import get_offset, verify_series


def short_run(fast, slow, length=None, offset=None, **kwargs):
    """Indicator: Short Run"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 2
    fast = verify_series(fast, length)
    slow = verify_series(slow, length)
    offset = get_offset(offset)

    if fast is None or slow is None: return

    # Calculate Result
    pt = decreasing(fast, length) & increasing(slow, length)  # potential top or top
    bd = decreasing(fast, length) & decreasing(slow, length)  # fast and slow are decreasing
    short_run = pt | bd

    # Offset
    if offset != 0:
        short_run = short_run.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        short_run.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        short_run.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    short_run.name = f"SR_{length}"
    short_run.category = "trend"

    return short_run
