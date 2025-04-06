# -*- coding: utf-8 -*-
from pandas import DataFrame, Series
from pandas_ta.overlap import ema
from pandas_ta.utils import get_offset, non_zero_range, verify_series


def stc(close, tclength=None, fast=None, slow=None, factor=None, offset=None, **kwargs):
    """Indicator: Schaff Trend Cycle (STC)"""
    # Validate arguments
    tclength = int(tclength) if tclength and tclength > 0 else 10
    fast = int(fast) if fast and fast > 0 else 12
    slow = int(slow) if slow and slow > 0 else 26
    factor = float(factor) if factor and factor > 0 else 0.5
    if slow < fast:                # mandatory condition, but might be confusing
        fast, slow = slow, fast
    _length = max(tclength, fast, slow)
    close = verify_series(close, _length)
    offset = get_offset(offset)

    if close is None: return

    # kwargs allows for three more series (ma1, ma2 and osc) which can be passed
    # here ma1 and ma2 input negate internal ema calculations, osc substitutes
    # both ma's.
    ma1 = kwargs.pop("ma1", False)
    ma2 = kwargs.pop("ma2", False)
    osc = kwargs.pop("osc", False)

    # 3 different modes of calculation..
    if isinstance(ma1, Series) and isinstance(ma2, Series) and not osc:
        ma1 = verify_series(ma1, _length)
        ma2 = verify_series(ma2, _length)

        if ma1 is None or ma2 is None: return
        # Calculate Result based on external feeded series
        xmacd = ma1 - ma2
        # invoke shared calculation
        pff, pf = schaff_tc(close, xmacd, tclength, factor)

    elif isinstance(osc, Series):
        osc = verify_series(osc, _length)
        if osc is None: return
        # Calculate Result based on feeded oscillator
        # (should be ranging around 0 x-axis)
        xmacd = osc
        # invoke shared calculation
        pff, pf = schaff_tc(close, xmacd, tclength, factor)

    else:
        # Calculate Result .. (traditionel/full)
        # MACD line
        fastma = ema(close, length=fast)
        slowma = ema(close, length=slow)
        xmacd = fastma - slowma
        # invoke shared calculation
        pff, pf = schaff_tc(close, xmacd, tclength, factor)

    # Resulting Series
    stc = Series(pff, index=close.index)
    macd = Series(xmacd, index=close.index)
    stoch = Series(pf, index=close.index)

    # Offset
    if offset != 0:
        stc = stc.shift(offset)
        macd = macd.shift(offset)
        stoch = stoch.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        stc.fillna(kwargs["fillna"], inplace=True)
        macd.fillna(kwargs["fillna"], inplace=True)
        stoch.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        stc.fillna(method=kwargs["fill_method"], inplace=True)
        macd.fillna(method=kwargs["fill_method"], inplace=True)
        stoch.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = f"_{tclength}_{fast}_{slow}_{factor}"
    stc.name = f"STC{_props}"
    macd.name = f"STCmacd{_props}"
    stoch.name = f"STCstoch{_props}"
    stc.category = macd.category = stoch.category ="momentum"

    # Prepare DataFrame to return
    data = {stc.name: stc, macd.name: macd, stoch.name: stoch}
    df = DataFrame(data)
    df.name = f"STC{_props}"
    df.category = stc.category

    return df


stc.__doc__ = \
"""Schaff Trend Cycle (STC)

The Schaff Trend Cycle is an evolution of the popular MACD incorportating two
cascaded stochastic calculations with additional smoothing.

The STC returns also the beginning MACD result as well as the result after the
first stochastic including its smoothing. This implementation has been extended
for Pandas TA to also allow for separatly feeding any other two moving Averages
(as ma1 and ma2) or to skip this to feed an oscillator (osc), based on which the
Schaff Trend Cycle should be calculated.

Feed external moving averages:
Internally calculation..
    stc = ta.stc(close=df["close"], tclen=stc_tclen, fast=ma1_interval, slow=ma2_interval, factor=stc_factor)
becomes..
    extMa1 = df.ta.zlma(close=df["close"], length=ma1_interval, append=True)
    extMa2 = df.ta.ema(close=df["close"], length=ma2_interval, append=True)
    stc = ta.stc(close=df["close"], tclen=stc_tclen, ma1=extMa1, ma2=extMa2, factor=stc_factor)

The same goes for osc=, which allows the input of an externally calculated oscillator, overriding ma1 & ma2.


Sources:
    Implemented by rengel8 based on work found here:
    https://www.prorealcode.com/prorealtime-indicators/schaff-trend-cycle2/

Calculation:
    STCmacd = Moving Average Convergance/Divergance or Oscillator
    STCstoch = Intermediate Stochastic of MACD/Osc.
    2nd Stochastic including filtering with results in the
    STC = Schaff Trend Cycle

Args:
    close (pd.Series): Series of 'close's, used for indexing Series, mandatory
    tclen (int): SchaffTC Signal-Line length.  Default: 10 (adjust to the half of cycle)
    fast (int): The short period.   Default: 12
    slow (int): The long period.   Default: 26
    factor (float): smoothing factor for last stoch. calculation.   Default: 0.5
    offset (int): How many periods to offset the result.  Default: 0

Kwargs:
    ma1: 1st moving average provided externally (mandatory in conjuction with ma2)
    ma2: 2nd moving average provided externally (mandatory in conjuction with ma1)
    osc: an externally feeded osillator
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: stc, macd, stoch
"""


def schaff_tc(close, xmacd, tclength, factor):
    # ACTUAL Calculation part, which is shared between operation modes
    # 1St : Stochastic of MACD
    lowest_xmacd = xmacd.rolling(tclength).min()  # min value in interval tclen
    xmacd_range = non_zero_range(xmacd.rolling(tclength).max(), lowest_xmacd)
    m = len(xmacd)

    # %Fast K of MACD
    stoch1, pf = list(xmacd), list(xmacd)
    stoch1[0], pf[0] = 0, 0
    for i in range(1, m):
        if lowest_xmacd[i] > 0:
            stoch1[i] = 100 * ((xmacd[i] - lowest_xmacd[i]) / xmacd_range[i])
        else:
            stoch1[i] = stoch1[i - 1]
        # Smoothed Calculation for % Fast D of MACD
        pf[i] = round(pf[i - 1] + (factor * (stoch1[i] - pf[i - 1])), 8)

    pf = Series(pf, index=close.index)

    # 2nd : Stochastic of smoothed Percent Fast D, 'PF', above
    lowest_pf = pf.rolling(tclength).min()
    pf_range = non_zero_range(pf.rolling(tclength).max(), lowest_pf)

    # % of Fast K of PF
    stoch2, pff = list(xmacd), list(xmacd)
    stoch2[0], pff[0] = 0, 0
    for i in range(1, m):
        if pf_range[i] > 0:
            stoch2[i] = 100 * ((pf[i] - lowest_pf[i]) / pf_range[i])
        else:
            stoch2[i] = stoch2[i - 1]
        # Smoothed Calculation for % Fast D of PF
        pff[i] = round(pff[i - 1] + (factor * (stoch2[i] - pff[i - 1])), 8)

    return [pff, pf]