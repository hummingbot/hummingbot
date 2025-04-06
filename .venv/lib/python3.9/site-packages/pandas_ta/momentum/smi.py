# -*- coding: utf-8 -*-
from pandas import DataFrame
from .tsi import tsi
from pandas_ta.overlap import ema
from pandas_ta.utils import get_offset, verify_series


def smi(close, fast=None, slow=None, signal=None, scalar=None, offset=None, **kwargs):
    """Indicator: SMI Ergodic Indicator (SMIIO)"""
    # Validate arguments
    fast = int(fast) if fast and fast > 0 else 5
    slow = int(slow) if slow and slow > 0 else 20
    signal = int(signal) if signal and signal > 0 else 5
    if slow < fast:
        fast, slow = slow, fast
    scalar = float(scalar) if scalar else 1
    close = verify_series(close, max(fast, slow, signal))
    offset = get_offset(offset)

    if close is None: return

    # Calculate Result
    tsi_df = tsi(close, fast=fast, slow=slow, signal=signal, scalar=scalar)
    smi = tsi_df.iloc[:, 0]
    signalma = tsi_df.iloc[:, 1]
    osc = smi - signalma

    # Offset
    if offset != 0:
        smi = smi.shift(offset)
        signalma = signalma.shift(offset)
        osc = osc.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        smi.fillna(kwargs["fillna"], inplace=True)
        signalma.fillna(kwargs["fillna"], inplace=True)
        osc.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        smi.fillna(method=kwargs["fill_method"], inplace=True)
        signalma.fillna(method=kwargs["fill_method"], inplace=True)
        osc.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _scalar = f"_{scalar}" if scalar != 1 else ""
    _props = f"_{fast}_{slow}_{signal}{_scalar}"
    smi.name = f"SMI{_props}"
    signalma.name = f"SMIs{_props}"
    osc.name = f"SMIo{_props}"
    smi.category = signalma.category = osc.category = "momentum"

    # Prepare DataFrame to return
    data = {smi.name: smi, signalma.name: signalma, osc.name: osc}
    df = DataFrame(data)
    df.name = f"SMI{_props}"
    df.category = smi.category

    return df


smi.__doc__ = \
"""SMI Ergodic Indicator (SMI)

The SMI Ergodic Indicator is the same as the True Strength Index (TSI) developed
by William Blau, except the SMI includes a signal line. The SMI uses double
moving averages of price minus previous price over 2 time frames. The signal
line, which is an EMA of the SMI, is plotted to help trigger trading signals.
The trend is bullish when crossing above zero and bearish when crossing below
zero. This implementation includes both the SMI Ergodic Indicator and SMI
Ergodic Oscillator.

Sources:
    https://www.motivewave.com/studies/smi_ergodic_indicator.htm
    https://www.tradingview.com/script/Xh5Q0une-SMI-Ergodic-Oscillator/
    https://www.tradingview.com/script/cwrgy4fw-SMIIO/

Calculation:
    Default Inputs:
        fast=5, slow=20, signal=5
    TSI = True Strength Index
    EMA = Exponential Moving Average

    ERG = TSI(close, fast, slow)
    Signal = EMA(ERG, signal)
    OSC = ERG - Signal

Args:
    close (pd.Series): Series of 'close's
    fast (int): The short period. Default: 5
    slow (int): The long period. Default: 20
    signal (int): The signal period. Default: 5
    scalar (float): How much to magnify. Default: 1
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: smi, signal, oscillator columns.
"""
