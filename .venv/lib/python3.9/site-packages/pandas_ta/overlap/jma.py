# -*- coding: utf-8 -*-
from numpy import average as npAverage
from numpy import nan as npNaN
from numpy import log as npLog
from numpy import power as npPower
from numpy import sqrt as npSqrt
from numpy import zeros_like as npZeroslike
from pandas import Series
from pandas_ta.utils import get_offset, verify_series


def jma(close, length=None, phase=None, offset=None, **kwargs):
    """Indicator: Jurik Moving Average (JMA)"""
    # Validate Arguments
    _length = int(length) if length and length > 0 else 7
    phase = float(phase) if phase and phase != 0 else 0
    close = verify_series(close, _length)
    offset = get_offset(offset)
    if close is None: return

    # Define base variables
    jma = npZeroslike(close)
    volty = npZeroslike(close)
    v_sum = npZeroslike(close)

    kv = det0 = det1 = ma2 = 0.0
    jma[0] = ma1 = uBand = lBand = close[0]

    # Static variables
    sum_length = 10
    length = 0.5 * (_length - 1)
    pr = 0.5 if phase < -100 else 2.5 if phase > 100 else 1.5 + phase * 0.01
    length1 = max((npLog(npSqrt(length)) / npLog(2.0)) + 2.0, 0)
    pow1 = max(length1 - 2.0, 0.5)
    length2 = length1 * npSqrt(length)
    bet = length2 / (length2 + 1)
    beta = 0.45 * (_length - 1) / (0.45 * (_length - 1) + 2.0)

    m = close.shape[0]
    for i in range(1, m):
        price = close[i]

        # Price volatility
        del1 = price - uBand
        del2 = price - lBand
        volty[i] = max(abs(del1),abs(del2)) if abs(del1)!=abs(del2) else 0

        # Relative price volatility factor
        v_sum[i] = v_sum[i - 1] + (volty[i] - volty[max(i - sum_length, 0)]) / sum_length
        avg_volty = npAverage(v_sum[max(i - 65, 0):i + 1])
        d_volty = 0 if avg_volty ==0 else volty[i] / avg_volty
        r_volty = max(1.0, min(npPower(length1, 1 / pow1), d_volty))

        # Jurik volatility bands
        pow2 = npPower(r_volty, pow1)
        kv = npPower(bet, npSqrt(pow2))
        uBand = price if (del1 > 0) else price - (kv * del1)
        lBand = price if (del2 < 0) else price - (kv * del2)

        # Jurik Dynamic Factor
        power = npPower(r_volty, pow1)
        alpha = npPower(beta, power)

        # 1st stage - prelimimary smoothing by adaptive EMA
        ma1 = ((1 - alpha) * price) + (alpha * ma1)

        # 2nd stage - one more prelimimary smoothing by Kalman filter
        det0 = ((price - ma1) * (1 - beta)) + (beta * det0)
        ma2 = ma1 + pr * det0

        # 3rd stage - final smoothing by unique Jurik adaptive filter
        det1 = ((ma2 - jma[i - 1]) * (1 - alpha) * (1 - alpha)) + (alpha * alpha * det1)
        jma[i] = jma[i-1] + det1

    # Remove initial lookback data and convert to pandas frame
    jma[0:_length - 1] = npNaN
    jma = Series(jma, index=close.index)

    # Offset
    if offset != 0:
        jma = jma.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        jma.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        jma.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    jma.name = f"JMA_{_length}_{phase}"
    jma.category = "overlap"

    return jma


jma.__doc__ = \
"""Jurik Moving Average Average (JMA)

Mark Jurik's Moving Average (JMA) attempts to eliminate noise to see the "true"
underlying activity. It has extremely low lag, is very smooth and is responsive
to market gaps.

Sources:
    https://c.mql5.com/forextsd/forum/164/jurik_1.pdf
    https://www.prorealcode.com/prorealtime-indicators/jurik-volatility-bands/

Calculation:
    Default Inputs:
        length=7, phase=0

Args:
    close (pd.Series): Series of 'close's
    length (int): Period of calculation. Default: 7
    phase (float): How heavy/light the average is [-100, 100]. Default: 0
    offset (int): How many lengths to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.Series: New feature generated.
"""
