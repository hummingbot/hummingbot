# -*- coding: utf-8 -*-
from numpy import arctan as npAtan
from numpy import pi as npPi
from pandas_ta.utils import get_offset, verify_series


def slope( close, length=None, as_angle=None, to_degrees=None, vertical=None, offset=None, **kwargs):
    """Indicator: Slope"""
    # Validate arguments
    length = int(length) if length and length > 0 else 1
    as_angle = True if isinstance(as_angle, bool) else False
    to_degrees = True if isinstance(to_degrees, bool) else False
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    slope = close.diff(length) / length
    if as_angle:
        slope = slope.apply(npAtan)
        if to_degrees:
            slope *= 180 / npPi

    # Offset
    if offset != 0:
        slope = slope.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        slope.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        slope.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    slope.name = f"SLOPE_{length}" if not as_angle else f"ANGLE{'d' if to_degrees else 'r'}_{length}"
    slope.category = "momentum"

    return slope


slope.__doc__ = \
"""Slope

Returns the slope of a series of length n. Can convert the slope to angle.
Default: slope.

Sources: Algebra I

Calculation:
    Default Inputs:
        length=1
    slope = close.diff(length) / length

    if as_angle:
        slope = slope.apply(atan)
        if to_degrees:
            slope *= 180 / PI

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period.  Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    as_angle (value, optional): Converts slope to an angle. Default: False
    to_degrees (value, optional): Converts slope angle to degrees. Default: False
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
