# -*- coding: utf-8 -*-
from numpy import sqrt as npSqrt
from pandas import DataFrame, Series
from pandas_ta.utils import get_offset, verify_series


def hwc(close, na=None, nb=None, nc=None, nd=None, scalar=None, channel_eval=None, offset=None, **kwargs):
    """Indicator: Holt-Winter Channel"""
    # Validate Arguments
    na = float(na) if na and na > 0 else 0.2
    nb = float(nb) if nb and nb > 0 else 0.1
    nc = float(nc) if nc and nc > 0 else 0.1
    nd = float(nd) if nd and nd > 0 else 0.1
    scalar = float(scalar) if scalar and scalar > 0 else 1
    channel_eval = bool(channel_eval) if channel_eval and channel_eval else False
    close = verify_series(close)
    offset = get_offset(offset)

    # Calculate Result
    last_a = last_v = last_var = 0
    last_f = last_price = last_result = close[0]
    lower, result, upper = [], [], []
    chan_pct_width, chan_width = [], []

    m = close.size
    for i in range(m):
        F = (1.0 - na) * (last_f + last_v + 0.5 * last_a) + na * close[i]
        V = (1.0 - nb) * (last_v + last_a) + nb * (F - last_f)
        A = (1.0 - nc) * last_a + nc * (V - last_v)
        result.append((F + V + 0.5 * A))

        var = (1.0 - nd) * last_var + nd * (last_price - last_result) * (last_price - last_result)
        stddev = npSqrt(last_var)
        upper.append(result[i] + scalar * stddev)
        lower.append(result[i] - scalar * stddev)

        if channel_eval:
            # channel width
            chan_width.append(upper[i] - lower[i])
            # channel percentage price position
            chan_pct_width.append((close[i] - lower[i]) / (upper[i] - lower[i]))
            # print('channel_eval (width|percentageWidth):', chan_width[i], chan_pct_width[i])

        # update values
        last_price = close[i]
        last_a = A
        last_f = F
        last_v = V
        last_var = var
        last_result = result[i]

    # Aggregate
    hwc = Series(result, index=close.index)
    hwc_upper = Series(upper, index=close.index)
    hwc_lower = Series(lower, index=close.index)
    if channel_eval:
        hwc_width = Series(chan_width, index=close.index)
        hwc_pctwidth = Series(chan_pct_width, index=close.index)

    # Offset
    if offset != 0:
        hwc = hwc.shift(offset)
        hwc_upper = hwc_upper.shift(offset)
        hwc_lower = hwc_lower.shift(offset)
        if channel_eval:
            hwc_width = hwc_width.shift(offset)
            hwc_pctwidth = hwc_pctwidth.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        hwc.fillna(kwargs["fillna"], inplace=True)
        hwc_upper.fillna(kwargs["fillna"], inplace=True)
        hwc_lower.fillna(kwargs["fillna"], inplace=True)
        if channel_eval:
            hwc_width.fillna(kwargs["fillna"], inplace=True)
            hwc_pctwidth.fillna(kwargs["fillna"], inplace=True)

    if "fill_method" in kwargs:
        hwc.fillna(method=kwargs["fill_method"], inplace=True)
        hwc_upper.fillna(method=kwargs["fill_method"], inplace=True)
        hwc_lower.fillna(method=kwargs["fill_method"], inplace=True)
        if channel_eval:
            hwc_width.fillna(method=kwargs["fill_method"], inplace=True)
            hwc_pctwidth.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    # suffix = f'{str(na).replace(".", "")}-{str(nb).replace(".", "")}-{str(nc).replace(".", "")}'
    hwc.name = "HWM"
    hwc_upper.name = "HWU"
    hwc_lower.name = "HWL"
    hwc.category = hwc_upper.category = hwc_lower.category = "volatility"
    if channel_eval:
        hwc_width.name = "HWW"
        hwc_pctwidth.name = "HWPCT"

    # Prepare DataFrame to return
    if channel_eval:
        data = {hwc.name: hwc, hwc_upper.name: hwc_upper, hwc_lower.name: hwc_lower,
                hwc_width.name: hwc_width, hwc_pctwidth.name: hwc_pctwidth}
        df = DataFrame(data)
        df.name = "HWC"
        df.category = hwc.category
    else:
        data = {hwc.name: hwc, hwc_upper.name: hwc_upper, hwc_lower.name: hwc_lower}
        df = DataFrame(data)
        df.name = "HWC"
        df.category = hwc.category

    return df



hwc.__doc__ = \
"""HWC (Holt-Winter Channel)

Channel indicator HWC (Holt-Winters Channel) based on HWMA - a three-parameter
moving average calculated by the method of Holt-Winters.

This version has been implemented for Pandas TA by rengel8 based on a
publication for MetaTrader 5 extended by width and percentage price position
against width of channel.

Sources:
    https://www.mql5.com/en/code/20857

Calculation:
    HWMA[i] = F[i] + V[i] + 0.5 * A[i]
    where..
    F[i] = (1-na) * (F[i-1] + V[i-1] + 0.5 * A[i-1]) + na * Price[i]
    V[i] = (1-nb) * (V[i-1] + A[i-1]) + nb * (F[i] - F[i-1])
    A[i] = (1-nc) * A[i-1] + nc * (V[i] - V[i-1])

    Top = HWMA + Multiplier * StDt
    Bottom = HWMA - Multiplier * StDt
    where..
    StDt[i] = Sqrt(Var[i-1])
    Var[i] = (1-d) * Var[i-1] + nD * (Price[i-1] - HWMA[i-1]) * (Price[i-1] - HWMA[i-1])

Args:
    na - parameter of the equation that describes a smoothed series (from 0 to 1)
    nb - parameter of the equation to assess the trend (from 0 to 1)
    nc - parameter of the equation to assess seasonality (from 0 to 1)
    nd - parameter of the channel equation (from 0 to 1)
    scaler - multiplier for the width of the channel calculated
    channel_eval - boolean to return width and percentage price position against price
    close (pd.Series): Series of 'close's

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method
Returns:
    pd.DataFrame: HWM (Mid), HWU (Upper), HWL (Lower) columns.
"""
