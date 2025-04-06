# -*- coding: utf-8 -*-
from pandas_ta.utils import verify_series
from numpy import nan as npNaN
from pandas import Series


def pvr(close, volume):
    """ Indicator: Price Volume Rank"""
    # Validate arguments
    close = verify_series(close)
    volume = verify_series(volume)

    # Calculate Result
    close_diff = close.diff().fillna(0)
    volume_diff = volume.diff().fillna(0)
    pvr_ = Series(npNaN, index=close.index)
    pvr_.loc[(close_diff >= 0) & (volume_diff >= 0)] = 1
    pvr_.loc[(close_diff >= 0) & (volume_diff < 0)]  = 2
    pvr_.loc[(close_diff < 0) & (volume_diff >= 0)]  = 3
    pvr_.loc[(close_diff < 0) & (volume_diff < 0)]   = 4

    # Name and Categorize it
    pvr_.name = f"PVR"
    pvr_.category = "volume"

    return pvr_


pvr.__doc__ = \
"""Price Volume Rank

The Price Volume Rank was developed by Anthony J. Macek and is described in his
article in the June, 1994 issue of Technical Analysis of Stocks & Commodities
Magazine. It was developed as a simple indicator that could be calculated even
without a computer. The basic interpretation is to buy when the PV Rank is below
2.5 and sell when it is above 2.5.

Sources:
    https://www.fmlabs.com/reference/default.htm?url=PVrank.htm

Calculation:
    return 1 if 'close change' >= 0 and 'volume change' >= 0
    return 2 if 'close change' >= 0 and 'volume change' < 0
    return 3 if 'close change' < 0 and 'volume change' >= 0
    return 4 if 'close change' < 0 and 'volume change' < 0

Args:
    close (pd.Series): Series of 'close's
    volume (pd.Series): Series of 'volume's

Returns:
    pd.Series: New feature generated.
"""
