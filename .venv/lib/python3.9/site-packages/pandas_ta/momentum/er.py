# -*- coding: utf-8 -*-
from pandas import DataFrame, concat
from pandas_ta.utils import get_drift, get_offset, verify_series, signals


def er(close, length=None, drift=None, offset=None, **kwargs):
    """Indicator: Efficiency Ratio (ER)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 10
    close = verify_series(close, length)
    offset = get_offset(offset)
    drift = get_drift(drift)

    if close is None: return

    # Calculate Result
    abs_diff = close.diff(length).abs()
    abs_volatility = close.diff(drift).abs()

    er = abs_diff
    er /= abs_volatility.rolling(window=length).sum()

    # Offset
    if offset != 0:
        er = er.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        er.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        er.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    er.name = f"ER_{length}"
    er.category = "momentum"

    signal_indicators = kwargs.pop("signal_indicators", False)
    if signal_indicators:
        signalsdf = concat(
            [
                DataFrame({er.name: er}),
                signals(
                    indicator=er,
                    xa=kwargs.pop("xa", 80),
                    xb=kwargs.pop("xb", 20),
                    xserie=kwargs.pop("xserie", None),
                    xserie_a=kwargs.pop("xserie_a", None),
                    xserie_b=kwargs.pop("xserie_b", None),
                    cross_values=kwargs.pop("cross_values", False),
                    cross_series=kwargs.pop("cross_series", True),
                    offset=offset,
                ),
            ],
            axis=1,
        )

        return signalsdf
    else:
        return er


er.__doc__ = \
"""Efficiency Ratio (ER)

The Efficiency Ratio was invented by Perry J. Kaufman and presented in his book "New Trading Systems and Methods". It is designed to account for market noise or volatility.

It is calculated by dividing the net change in price movement over N periods by the sum of the absolute net changes over the same N periods.

Sources:
    https://help.tc2000.com/m/69404/l/749623-kaufman-efficiency-ratio

Calculation:
    Default Inputs:
        length=10
    ABS = Absolute Value
    EMA = Exponential Moving Average

    abs_diff = ABS(close.diff(length))
    volatility = ABS(close.diff(1))
    ER = abs_diff / SUM(volatility, length)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
