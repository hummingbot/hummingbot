# -*- coding: utf-8 -*-
from pandas import DataFrame, concat
from pandas_ta import Imports
from pandas_ta.overlap import rma
from pandas_ta.utils import get_drift, get_offset, verify_series, signals


def rsi(close, length=None, scalar=None, talib=None, drift=None, offset=None, **kwargs):
    """Indicator: Relative Strength Index (RSI)"""
    # Validate arguments
    length = int(length) if length and length > 0 else 14
    scalar = float(scalar) if scalar else 100
    close = verify_series(close, length)
    drift = get_drift(drift)
    offset = get_offset(offset)
    mode_tal = bool(talib) if isinstance(talib, bool) else True

    if close is None: return

    # Calculate Result
    if Imports["talib"] and mode_tal:
        from talib import RSI
        rsi = RSI(close, length)
    else:
        negative = close.diff(drift)
        positive = negative.copy()

        positive[positive < 0] = 0  # Make negatives 0 for the postive series
        negative[negative > 0] = 0  # Make postives 0 for the negative series

        positive_avg = rma(positive, length=length)
        negative_avg = rma(negative, length=length)

        rsi = scalar * positive_avg / (positive_avg + negative_avg.abs())

    # Offset
    if offset != 0:
        rsi = rsi.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        rsi.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        rsi.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    rsi.name = f"RSI_{length}"
    rsi.category = "momentum"

    signal_indicators = kwargs.pop("signal_indicators", False)
    if signal_indicators:
        signalsdf = concat(
            [
                DataFrame({rsi.name: rsi}),
                signals(
                    indicator=rsi,
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
        return rsi


rsi.__doc__ = \
"""Relative Strength Index (RSI)

The Relative Strength Index is popular momentum oscillator used to measure the
velocity as well as the magnitude of directional price movements.

Sources:
    https://www.tradingview.com/wiki/Relative_Strength_Index_(RSI)

Calculation:
    Default Inputs:
        length=14, scalar=100, drift=1
    ABS = Absolute Value
    RMA = Rolling Moving Average

    diff = close.diff(drift)
    positive = diff if diff > 0 else 0
    negative = diff if diff < 0 else 0

    pos_avg = RMA(positive, length)
    neg_avg = ABS(RMA(negative, length))

    RSI = scalar * pos_avg / (pos_avg + neg_avg)

Args:
    close (pd.Series): Series of 'close's
    length (int): It's period. Default: 14
    scalar (float): How much to magnify. Default: 100
    talib (bool): If TA Lib is installed and talib is True, Returns the TA Lib
        version. Default: True
    drift (int): The difference period. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
