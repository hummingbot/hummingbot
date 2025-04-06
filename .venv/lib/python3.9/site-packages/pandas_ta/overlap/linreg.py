# -*- coding: utf-8 -*-
from numpy import array as npArray
from numpy import arctan as npAtan
from numpy import nan as npNaN
from numpy import pi as npPi
from numpy.version import version as npVersion
from pandas import Series
from pandas_ta.utils import get_offset, verify_series


def linreg(close, length=None, offset=None, **kwargs):
    """Indicator: Linear Regression"""
    # Validate arguments
    length = int(length) if length and length > 0 else 14
    close = verify_series(close, length)
    offset = get_offset(offset)
    angle = kwargs.pop("angle", False)
    intercept = kwargs.pop("intercept", False)
    degrees = kwargs.pop("degrees", False)
    r = kwargs.pop("r", False)
    slope = kwargs.pop("slope", False)
    tsf = kwargs.pop("tsf", False)

    if close is None: return

    # Calculate Result
    x = range(1, length + 1)  # [1, 2, ..., n] from 1 to n keeps Sum(xy) low
    x_sum = 0.5 * length * (length + 1)
    x2_sum = x_sum * (2 * length + 1) / 3
    divisor = length * x2_sum - x_sum * x_sum

    def linear_regression(series):
        y_sum = series.sum()
        xy_sum = (x * series).sum()

        m = (length * xy_sum - x_sum * y_sum) / divisor
        if slope:
            return m
        b = (y_sum * x2_sum - x_sum * xy_sum) / divisor
        if intercept:
            return b

        if angle:
            theta = npAtan(m)
            if degrees:
                theta *= 180 / npPi
            return theta

        if r:
            y2_sum = (series * series).sum()
            rn = length * xy_sum - x_sum * y_sum
            rd = (divisor * (length * y2_sum - y_sum * y_sum)) ** 0.5
            return rn / rd

        return m * length + b if tsf else m * (length - 1) + b

    def rolling_window(array, length):
        """https://github.com/twopirllc/pandas-ta/issues/285"""
        strides = array.strides + (array.strides[-1],)
        shape = array.shape[:-1] + (array.shape[-1] - length + 1, length)
        return as_strided(array, shape=shape, strides=strides)

    if npVersion >= "1.20.0":
        from numpy.lib.stride_tricks import sliding_window_view
        linreg_ = [linear_regression(_) for _ in sliding_window_view(npArray(close), length)]
    else:
        from numpy.lib.stride_tricks import as_strided
        linreg_ = [linear_regression(_) for _ in rolling_window(npArray(close), length)]

    linreg = Series([npNaN] * (length - 1) + linreg_, index=close.index)

    # Offset
    if offset != 0:
        linreg = linreg.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        linreg.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        linreg.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    linreg.name = f"LR"
    if slope: linreg.name += "m"
    if intercept: linreg.name += "b"
    if angle: linreg.name += "a"
    if r: linreg.name += "r"

    linreg.name += f"_{length}"
    linreg.category = "overlap"

    return linreg


linreg.__doc__ = \
"""Linear Regression Moving Average (linreg)

Linear Regression Moving Average (LINREG). This is a simplified version of a
Standard Linear Regression. LINREG is a rolling regression of one variable. A
Standard Linear Regression is between two or more variables.

Source: TA Lib

Calculation:
    Default Inputs:
        length=14
    x = [1, 2, ..., n]
    x_sum = 0.5 * length * (length + 1)
    x2_sum = length * (length + 1) * (2 * length + 1) / 6
    divisor = length * x2_sum - x_sum * x_sum

    lr(series):
        y_sum = series.sum()
        y2_sum = (series* series).sum()
        xy_sum = (x * series).sum()

        m = (length * xy_sum - x_sum * y_sum) / divisor
        b = (y_sum * x2_sum - x_sum * xy_sum) / divisor
        return m * (length - 1) + b

    linreg = close.rolling(length).apply(lr)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period.  Default: 10
    offset (int): How many periods to offset the result.  Default: 0

Kwargs:
    angle (bool, optional): If True, returns the angle of the slope in radians.
        Default: False.
    degrees (bool, optional): If True, returns the angle of the slope in
        degrees. Default: False.
    intercept (bool, optional): If True, returns the angle of the slope in
        radians. Default: False.
    r (bool, optional): If True, returns it's correlation 'r'. Default: False.
    slope (bool, optional): If True, returns the slope. Default: False.
    tsf (bool, optional): If True, returns the Time Series Forecast value.
        Default: False.
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
