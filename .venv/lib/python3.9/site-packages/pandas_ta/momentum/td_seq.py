# -*- coding: utf-8 -*-
# import numpy as np
from numpy import where as npWhere
from pandas import DataFrame, Series
from pandas_ta.utils import get_offset, verify_series


def td_seq(close, asint=None, offset=None, **kwargs):
    """Indicator: Tom Demark Sequential (TD_SEQ)"""
    # Validate arguments
    close = verify_series(close)
    offset = get_offset(offset)
    asint = asint if isinstance(asint, bool) else False
    show_all = kwargs.setdefault("show_all", True)

    def true_sequence_count(series: Series):
        index = series.where(series == False).last_valid_index()

        if index is None:
            return series.count()
        else:
            s = series[series.index > index]
            return s.count()

    def calc_td(series: Series, direction: str, show_all: bool):
        td_bool = series.diff(4) > 0 if direction=="up" else series.diff(4) < 0
        td_num = npWhere(
            td_bool, td_bool.rolling(13, min_periods=0).apply(true_sequence_count), 0
        )
        td_num = Series(td_num)

        if show_all:
            td_num = td_num.mask(td_num == 0)
        else:
            td_num = td_num.mask(~td_num.between(6,9))

        return td_num

    up_seq = calc_td(close, "up", show_all)
    down_seq = calc_td(close, "down", show_all)

    if asint:
        if up_seq.hasnans and down_seq.hasnans:
            up_seq.fillna(0, inplace=True)
            down_seq.fillna(0, inplace=True)
        up_seq = up_seq.astype(int)
        down_seq = down_seq.astype(int)

     # Offset
    if offset != 0:
        up_seq = up_seq.shift(offset)
        down_seq = down_seq.shift(offset)

    # Handle fills
    if "fillna" in kwargs:
        up_seq.fillna(kwargs["fillna"], inplace=True)
        down_seq.fillna(kwargs["fillna"], inplace=True)

    if "fill_method" in kwargs:
        up_seq.fillna(method=kwargs["fill_method"], inplace=True)
        down_seq.fillna(method=kwargs["fill_method"], inplace=True)

    # Name & Category
    up_seq.name = f"TD_SEQ_UPa" if show_all else f"TD_SEQ_UP"
    down_seq.name = f"TD_SEQ_DNa" if show_all else f"TD_SEQ_DN"
    up_seq.category = down_seq.category = "momentum"

    # Prepare Dataframe to return
    df = DataFrame({up_seq.name: up_seq, down_seq.name: down_seq})
    df.name = "TD_SEQ"
    df.category = up_seq.category

    return df


td_seq.__doc__ = \
"""TD Sequential (TD_SEQ)

Tom DeMark's Sequential indicator attempts to identify a price point where an
uptrend or a downtrend exhausts itself and reverses.

Sources:
    https://tradetrekker.wordpress.com/tdsequential/

Calculation:
    Compare current close price with 4 days ago price, up to 13 days. For the
    consecutive ascending or descending price sequence, display 6th to 9th day
    value.

Args:
    close (pd.Series): Series of 'close's
    asint (bool): If True, fillnas with 0 and change type to int. Default: False
    offset (int): How many periods to offset the result. Default: 0

Kwargs:
    show_all (bool): Show 1 - 13. If set to False, show 6 - 9. Default: True
    fillna (value, optional): pd.DataFrame.fillna(value)

Returns:
    pd.DataFrame: New feature generated.
"""