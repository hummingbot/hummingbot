# -*- coding: utf-8 -*-
from numpy import NaN as npNaN
from pandas import DataFrame
from pandas_ta.momentum import mom
from pandas_ta.overlap import ema, sma
from pandas_ta.trend import decreasing, increasing
from pandas_ta.volatility import bbands, kc
from pandas_ta.utils import get_offset
from pandas_ta.utils import unsigned_differences, verify_series


def squeeze_pro(high, low, close, bb_length=None, bb_std=None, kc_length=None, kc_scalar_wide=None, kc_scalar_normal=None, kc_scalar_narrow=None, mom_length=None, mom_smooth=None, use_tr=None, mamode=None, offset=None, **kwargs):
    """Indicator: Squeeze Momentum (SQZ) PRO"""
    # Validate arguments
    bb_length = int(bb_length) if bb_length and bb_length > 0 else 20
    bb_std = float(bb_std) if bb_std and bb_std > 0 else 2.0
    kc_length = int(kc_length) if kc_length and kc_length > 0 else 20
    kc_scalar_wide = float(kc_scalar_wide) if kc_scalar_wide and kc_scalar_wide > 0 else 2
    kc_scalar_normal = float(kc_scalar_normal) if kc_scalar_normal and kc_scalar_normal > 0 else 1.5
    kc_scalar_narrow = float(kc_scalar_narrow) if kc_scalar_narrow and kc_scalar_narrow > 0 else 1
    mom_length = int(mom_length) if mom_length and mom_length > 0 else 12
    mom_smooth = int(mom_smooth) if mom_smooth and mom_smooth > 0 else 6

    _length = max(bb_length, kc_length, mom_length, mom_smooth)
    high = verify_series(high, _length)
    low = verify_series(low, _length)
    close = verify_series(close, _length)
    offset = get_offset(offset)

    valid_kc_scaler = kc_scalar_wide > kc_scalar_normal and kc_scalar_normal > kc_scalar_narrow

    if not valid_kc_scaler: return
    if high is None or low is None or close is None: return

    use_tr = kwargs.setdefault("tr", True)
    asint = kwargs.pop("asint", True)
    detailed = kwargs.pop("detailed", False)
    mamode = mamode if isinstance(mamode, str) else "sma"

    def simplify_columns(df, n=3):
        df.columns = df.columns.str.lower()
        return [c.split("_")[0][n - 1:n] for c in df.columns]

    # Calculate Result
    bbd = bbands(close, length=bb_length, std=bb_std, mamode=mamode)
    kch_wide = kc(high, low, close, length=kc_length, scalar=kc_scalar_wide, mamode=mamode, tr=use_tr)
    kch_normal = kc(high, low, close, length=kc_length, scalar=kc_scalar_normal, mamode=mamode, tr=use_tr)
    kch_narrow = kc(high, low, close, length=kc_length, scalar=kc_scalar_narrow, mamode=mamode, tr=use_tr)

    # Simplify KC and BBAND column names for dynamic access
    bbd.columns = simplify_columns(bbd)
    kch_wide.columns = simplify_columns(kch_wide)
    kch_normal.columns = simplify_columns(kch_normal)
    kch_narrow.columns = simplify_columns(kch_narrow)

    momo = mom(close, length=mom_length)
    if mamode.lower() == "ema":
        squeeze = ema(momo, length=mom_smooth)
    else: # "sma"
        squeeze = sma(momo, length=mom_smooth)

    # Classify Squeezes
    squeeze_on_wide = (bbd.l > kch_wide.l) & (bbd.u < kch_wide.u)
    squeeze_on_normal = (bbd.l > kch_normal.l) & (bbd.u < kch_normal.u)
    squeeze_on_narrow = (bbd.l > kch_narrow.l) & (bbd.u < kch_narrow.u)
    squeeze_off_wide = (bbd.l < kch_wide.l) & (bbd.u > kch_wide.u)
    no_squeeze = ~squeeze_on_wide & ~squeeze_off_wide

    # Offset
    if offset != 0:
        squeeze = squeeze.shift(offset)
        squeeze_on_wide = squeeze_on_wide.shift(offset)
        squeeze_on_normal = squeeze_on_normal.shift(offset)
        squeeze_on_narrow = squeeze_on_narrow.shift(offset)
        squeeze_off_wide = squeeze_off_wide.shift(offset)
        no_squeeze = no_squeeze.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        squeeze.fillna(kwargs["fillna"], inplace=True)
        squeeze_on_wide.fillna(kwargs["fillna"], inplace=True)
        squeeze_on_normal.fillna(kwargs["fillna"], inplace=True)
        squeeze_on_narrow.fillna(kwargs["fillna"], inplace=True)
        squeeze_off_wide.fillna(kwargs["fillna"], inplace=True)
        no_squeeze.fillna(kwargs["fillna"], inplace=True)
    if "fill_method" in kwargs:
        squeeze.fillna(method=kwargs["fill_method"], inplace=True)
        squeeze_on_wide.fillna(method=kwargs["fill_method"], inplace=True)
        squeeze_on_normal.fillna(method=kwargs["fill_method"], inplace=True)
        squeeze_on_narrow.fillna(method=kwargs["fill_method"], inplace=True)
        squeeze_off_wide.fillna(method=kwargs["fill_method"], inplace=True)
        no_squeeze.fillna(method=kwargs["fill_method"], inplace=True)

    # Name and Categorize it
    _props = "" if use_tr else "hlr"
    _props += f"_{bb_length}_{bb_std}_{kc_length}_{kc_scalar_wide}_{kc_scalar_normal}_{kc_scalar_narrow}"
    squeeze.name = f"SQZPRO{_props}"

    data = {
        squeeze.name: squeeze,
        f"SQZPRO_ON_WIDE": squeeze_on_wide.astype(int) if asint else squeeze_on_wide,
        f"SQZPRO_ON_NORMAL": squeeze_on_normal.astype(int) if asint else squeeze_on_normal,
        f"SQZPRO_ON_NARROW": squeeze_on_narrow.astype(int) if asint else squeeze_on_narrow,
        f"SQZPRO_OFF": squeeze_off_wide.astype(int) if asint else squeeze_off_wide,
        f"SQZPRO_NO": no_squeeze.astype(int) if asint else no_squeeze,
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

        df[f"SQZPRO_INC"] = sqz_inc
        df[f"SQZPRO_DEC"] = sqz_dec
        df[f"SQZPRO_PINC"] = pos_inc
        df[f"SQZPRO_PDEC"] = pos_dec
        df[f"SQZPRO_NDEC"] = neg_dec
        df[f"SQZPRO_NINC"] = neg_inc

    return df


squeeze_pro.__doc__ = \
"""Squeeze PRO(SQZPRO)

This indicator is an extended version of "TTM Squeeze" from John Carter.
The default is based on John Carter's "TTM Squeeze" indicator, as discussed
in his book "Mastering the Trade" (chapter 11). The Squeeze indicator attempts
to capture the relationship between two studies: Bollinger Bands® and Keltner's
Channels. When the volatility increases, so does the distance between the bands,
conversely, when the volatility declines, the distance also decreases. It finds
sections of the Bollinger Bands® study which fall inside the Keltner's Channels.

Sources:
    https://usethinkscript.com/threads/john-carters-squeeze-pro-indicator-for-thinkorswim-free.4021/
    https://www.tradingview.com/script/TAAt6eRX-Squeeze-PRO-Indicator-Makit0/

Calculation:
    Default Inputs:
        bb_length=20, bb_std=2, kc_length=20, kc_scalar_wide=2,
        kc_scalar_normal=1.5, kc_scalar_narrow=1, mom_length=12,
        mom_smooth=6, tr=True,
    BB = Bollinger Bands
    KC = Keltner Channels
    MOM = Momentum
    SMA = Simple Moving Average
    EMA = Exponential Moving Average
    TR = True Range

    RANGE = TR(high, low, close) if using_tr else high - low
    BB_LOW, BB_MID, BB_HIGH = BB(close, bb_length, std=bb_std)
    KC_LOW_WIDE, KC_MID_WIDE, KC_HIGH_WIDE = KC(high, low, close, kc_length, kc_scalar_wide, TR)
    KC_LOW_NORMAL, KC_MID_NORMAL, KC_HIGH_NORMAL = KC(high, low, close, kc_length, kc_scalar_normal, TR)
    KC_LOW_NARROW, KC_MID_NARROW, KC_HIGH_NARROW = KC(high, low, close, kc_length, kc_scalar_narrow, TR)

    MOMO = MOM(close, mom_length)
    if mamode == "ema":
        SQZPRO = EMA(MOMO, mom_smooth)
    else:
        SQZPRO = EMA(momo, mom_smooth)

    SQZPRO_ON_WIDE  = (BB_LOW > KC_LOW_WIDE) and (BB_HIGH < KC_HIGH_WIDE)
    SQZPRO_ON_NORMAL  = (BB_LOW > KC_LOW_NORMAL) and (BB_HIGH < KC_HIGH_NORMAL)
    SQZPRO_ON_NARROW  = (BB_LOW > KC_LOW_NARROW) and (BB_HIGH < KC_HIGH_NARROW)
    SQZPRO_OFF_WIDE = (BB_LOW < KC_LOW_WIDE) and (BB_HIGH > KC_HIGH_WIDE)
    SQZPRO_NO = !SQZ_ON_WIDE and !SQZ_OFF_WIDE

Args:
    high (pd.Series): Series of 'high's
    low (pd.Series): Series of 'low's
    close (pd.Series): Series of 'close's
    bb_length (int): Bollinger Bands period. Default: 20
    bb_std (float): Bollinger Bands Std. Dev. Default: 2
    kc_length (int): Keltner Channel period. Default: 20
    kc_scalar_wide (float): Keltner Channel scalar for wider channel. Default: 2
    kc_scalar_normal (float): Keltner Channel scalar for normal channel. Default: 1.5
    kc_scalar_narrow (float): Keltner Channel scalar for narrow channel. Default: 1
    mom_length (int): Momentum Period. Default: 12
    mom_smooth (int): Smoothing Period of Momentum. Default: 6
    mamode (str): Only "ema" or "sma". Default: "sma"
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    tr (value, optional): Use True Range for Keltner Channels. Default: True
    asint (value, optional): Use integers instead of bool. Default: True
    mamode (value, optional): Which MA to use. Default: "sma"
    detailed (value, optional): Return additional variations of SQZ for
        visualization. Default: False
    fillna (value, optional): pd.DataFrame.fillna(value)
    fill_method (value, optional): Type of fill method

Returns:
    pd.DataFrame: SQZPRO, SQZPRO_ON_WIDE, SQZPRO_ON_NORMAL, SQZPRO_ON_NARROW, SQZPRO_OFF_WIDE, SQZPRO_NO columns by default. More
        detailed columns if 'detailed' kwarg is True.
"""
