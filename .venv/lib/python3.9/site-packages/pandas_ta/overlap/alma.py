# -*- coding: utf-8 -*-
from numpy import exp as npExp
from numpy import nan as npNaN
from pandas import Series
from pandas_ta.utils import get_offset, verify_series


def alma(close, length=None, sigma=None, distribution_offset=None, offset=None, **kwargs):
    """Indicator: Arnaud Legoux Moving Average (ALMA)"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 10
    sigma = float(sigma) if sigma and sigma > 0 else 6.0
    distribution_offset = float(distribution_offset) if distribution_offset and distribution_offset > 0 else 0.85
    close = verify_series(close, length)
    offset = get_offset(offset)

    if close is None: return

    # Pre-Calculations
    m = distribution_offset * (length - 1)
    s = length / sigma
    wtd = list(range(length))
    for i in range(0, length):
        wtd[i] = npExp(-1 * ((i - m) * (i - m)) / (2 * s * s))

    # Calculate Result
    result = [npNaN for _ in range(0, length - 1)] + [0]
    for i in range(length, close.size):
        window_sum = 0
        cum_sum = 0
        for j in range(0, length):
            # wtd = math.exp(-1 * ((j - m) * (j - m)) / (2 * s * s))        # moved to pre-calc for efficiency
            window_sum = window_sum + wtd[j] * close.iloc[i - j]
            cum_sum = cum_sum + wtd[j]

        almean = window_sum / cum_sum
        result.append(npNaN) if i == length else result.append(almean)

    alma = Series(result, index=close.index)

    # Offset
    if offset != 0:
        alma = alma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        alma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        alma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    alma.name = f"ALMA_{length}_{sigma}_{distribution_offset}"
    alma.category = "overlap"

    return alma


alma.__doc__ = \
"""Arnaud Legoux Moving Average (ALMA)

The ALMA moving average uses the curve of the Normal (Gauss) distribution, which
can be shifted from 0 to 1. This allows regulating the smoothness and high
sensitivity of the indicator. Sigma is another parameter that is responsible for
the shape of the curve coefficients. This moving average reduces lag of the data
in conjunction with smoothing to reduce noise.

Implemented for Pandas TA by rengel8 based on the source provided below.

Sources:
    https://www.prorealcode.com/prorealtime-indicators/alma-arnaud-legoux-moving-average/

Calculation:
    refer to provided source

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period, window size. Default: 10
    sigma (float): Smoothing value. Default 6.0
    distribution_offset (float): Value to offset the distribution min 0
        (smoother), max 1 (more responsive). Default 0.85
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
