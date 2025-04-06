# -*- coding: utf-8 -*-
from numpy import nan as npNaN
from pandas import DataFrame
from pandas_ta.momentum import mom
from pandas_ta.overlap import ema, linreg, sma
from pandas_ta.trend import decreasing, increasing
from pandas_ta.volatility import bbands, kc
from pandas_ta.utils import get_offset
from pandas_ta.utils import unsigned_differences, verify_series


def squeeze(high, low, close, bb_length=None, bb_std=None, kc_length=None, kc_scalar=None, mom_length=None, mom_smooth=None, use_tr=None, mamode=None, offset=None, **kwargs):
    """Indicator: Squeeze Momentum (SQZ)"""
    # Validate arguments
    bb_length = int(bb_length) if bb_length and bb_length > 0 else 20
    bb_std = float(bb_std) if bb_std and bb_std > 0 else 2.0
    kc_length = int(kc_length) if kc_length and kc_length > 0 else 20
    kc_scalar = float(kc_scalar) if kc_scalar and kc_scalar > 0 else 1.5
    mom_length = int(mom_length) if mom_length and mom_length > 0 else 12
    mom_smooth = int(mom_smooth) if mom_smooth and mom_smooth > 0 else 6
    _length = max(bb_length, kc_length, mom_length, mom_smooth)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)

    if high is None or low is None or close is None: return

    use_tr = kwargs.setdefault("tr", True)
    asint = kwargs.pop("asint", True)
    detailed = kwargs.pop("detailed", False)
    lazybear = kwargs.pop("lazybear", False)
    mamode = mamode if isinstance(mamode, str) else "sma"

    def simplify_columns(df, n=3):
        df.columns = df.columns.str.lower()
        return [c.split("_")[0][n - 1:n] for c in df.columns]

    # Calculate Result
    bbd = bbands(close, length=bb_length, std=bb_std, mamode=mamode)
    kch = kc(high, low, close, length=kc_length, scalar=kc_scalar, mamode=mamode, tr=use_tr)

    # Simplify KC and BBAND column names for dynamic access
    bbd.columns = simplify_columns(bbd)
    kch.columns = simplify_columns(kch)

    if lazybear:
        highest_high = high.rolling(kc_length).max()
        lowest_low = low.rolling(kc_length).min()
        avg_ = 0.25 * (highest_high + lowest_low) + 0.5 * kch.b

        squeeze = linreg(close - avg_, length=kc_length)

    else:
        momo = mom(close, length=mom_length)
        if mamode.lower() == "ema":
            squeeze = ema(momo, length=mom_smooth)
        else: # "sma"
            squeeze = sma(momo, length=mom_smooth)

    # Classify Squeezes
    squeeze_on = (bbd.l > kch.l) & (bbd.u < kch.u)
    squeeze_off = (bbd.l < kch.l) & (bbd.u > kch.u)
    no_squeeze = ~squeeze_on & ~squeeze_off

    # Offset
    if offset != 0:
        squeeze = squeeze.shift(offset)
        squeeze_on = squeeze_on.shift(offset)
        squeeze_off = squeeze_off.shift(offset)
        no_squeeze = no_squeeze.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        squeeze.fillna(kwargs["fillna"], inplace=True)
        squeeze_on.fillna(kwargs["fillna"], inplace=True)
        squeeze_off.fillna(kwargs["fillna"], inplace=True)
        no_squeeze.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        squeeze.fillna(method=kwargs["fill_method"], inplace=True)
        squeeze_on.fillna(method=kwargs["fill_method"], inplace=True)
        squeeze_off.fillna(method=kwargs["fill_method"], inplace=True)
        no_squeeze.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = "" if use_tr else "hlr"
    _props += f"_{bb_length}_{bb_std}_{kc_length}_{kc_scalar}"
    _props += "_LB" if lazybear else ""
    squeeze.name = f"SQZ{_props}"

    data = {
        squeeze.name: squeeze,
        f"SQZ_ON": squeeze_on.astype(int) if asint else squeeze_on,
        f"SQZ_OFF": squeeze_off.astype(int) if asint else squeeze_off,
        f"SQZ_NO": no_squeeze.astype(int) if asint else no_squeeze,
    }
    df = DataFrame(data)
    df.name = squeeze.name
    df.category = squeeze.category = "momentum"

    # Detailed Squeeze Series
    if detailed:
        pos_squeeze = squeeze[squeeze >= 0]
        neg_squeeze = squeeze[squeeze < 0]

        pos_inc, pos_dec = unsigned_differences(pos_squeeze, asint=True)
        neg_inc, neg_dec = unsigned_differences(neg_squeeze, asint=True)

        pos_inc *= squeeze
        pos_dec *= squeeze
        neg_dec *= squeeze
        neg_inc *= squeeze

        pos_inc.replace(0, npNaN, inplace=True)
        pos_dec.replace(0, npNaN, inplace=True)
        neg_dec.replace(0, npNaN, inplace=True)
        neg_inc.replace(0, npNaN, inplace=True)

        sqz_inc = squeeze * increasing(squeeze)
        sqz_dec = squeeze * decreasing(squeeze)
        sqz_inc.replace(0, npNaN, inplace=True)
        sqz_dec.replace(0, npNaN, inplace=True)

        # Handle fills
        if "fillna" in kwargs:
            sqz_inc.fillna(kwargs["fillna"], inplace=True)
            sqz_dec.fillna(kwargs["fillna"], inplace=True)
            pos_inc.fillna(kwargs["fillna"], inplace=True)
            pos_dec.fillna(kwargs["fillna"], inplace=True)
            neg_dec.fillna(kwargs["fillna"], inplace=True)
            neg_inc.fillna(kwargs["fillna"], inplace=True)
        if "fill_method" in kwargs:
            sqz_inc.fillna(method=kwargs["fill_method"], inplace=True)
            sqz_dec.fillna(method=kwargs["fill_method"], inplace=True)
            pos_inc.fillna(method=kwargs["fill_method"], inplace=True)
            pos_dec.fillna(method=kwargs["fill_method"], inplace=True)
            neg_dec.fillna(method=kwargs["fill_method"], inplace=True)
            neg_inc.fillna(method=kwargs["fill_method"], inplace=True)

        df[f"SQZ_INC"] = sqz_inc
        df[f"SQZ_DEC"] = sqz_dec
        df[f"SQZ_PINC"] = pos_inc
        df[f"SQZ_PDEC"] = pos_dec
        df[f"SQZ_NDEC"] = neg_dec
        df[f"SQZ_NINC"] = neg_inc

    return df


squeeze.__doc__ = \
"""Squeeze (SQZ)

The default is based on John Carter's "TTM Squeeze" indicator, as discussed
in his book "Mastering the Trade" (chapter 11). The Squeeze indicator attempts
to capture the relationship between two studies: Bollinger Bands® and Keltner's
Channels. When the volatility increases, so does the distance between the bands,
conversely, when the volatility declines, the distance also decreases. It finds
sections of the Bollinger Bands® study which fall inside the Keltner's Channels.

Sources:
    https://tradestation.tradingappstore.com/products/TTMSqueeze
    https://www.tradingview.com/scripts/lazybear/
    https://tlc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze

Calculation:
    Default Inputs:
        bb_length=20, bb_std=2, kc_length=20, kc_scalar=1.5, mom_length=12,
        mom_smooth=12, tr=True, lazybear=False,
    BB = Bollinger Bands
    KC = Keltner Channels
    MOM = Momentum
    SMA = Simple Moving Average
    EMA = Exponential Moving Average
    TR = True Range

    RANGE = TR(high, low, close) if using_tr else high - low
    BB_LOW, BB_MID, BB_HIGH = BB(close, bb_length, std=bb_std)
    KC_LOW, KC_MID, KC_HIGH = KC(high, low, close, kc_length, kc_scalar, TR)

    if lazybear:
        HH = high.rolling(kc_length).max()
        LL = low.rolling(kc_length).min()
        AVG  = 0.25 * (HH + LL) + 0.5 * KC_MID
        SQZ = linreg(close - AVG, kc_length)
    else:
        MOMO = MOM(close, mom_length)
        if mamode == "ema":
            SQZ = EMA(MOMO, mom_smooth)
        else:
            SQZ = EMA(momo, mom_smooth)

    SQZ_ON  = (BB_LOW > KC_LOW) and (BB_HIGH < KC_HIGH)
    SQZ_OFF = (BB_LOW < KC_LOW) and (BB_HIGH > KC_HIGH)
    NO_SQZ = !SQZ_ON and !SQZ_OFF

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    bb_length (int): Bollinger Bands period. Default: 20
    bb_std (float): Bollinger Bands Std. Dev. Default: 2
    kc_length (int): Keltner Channel period. Default: 20
    kc_scalar (float): Keltner Channel scalar. Default: 1.5
    mom_length (int): Momentum Period. Default: 12
    mom_smooth (int): Smoothing Period of Momentum. Default: 6
    mamode (str): Only "ema" or "sma". Default: "sma"
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    tr (value, optional): Use True Range for Keltner Channels. Default: True
    asint (value, optional): Use integers instead of bool. Default: True
    mamode (value, optional): Which MA to use. Default: "sma"
    lazybear (value, optional): Use LazyBear's TradingView implementation.
        Default: False
    detailed (value, optional): Return additional variations of SQZ for
        visualization. Default: False
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: SQZ, SQZ_ON, SQZ_OFF, NO_SQZ columns by default. More
        detailed columns if 'detailed' kwarg is True.
"""
