# -*- coding: utf-8 -*-
from pandas import Series

from .dema import dema
from .ema import ema
from .fwma import fwma
from .hma import hma
from .linreg import linreg
from .midpoint import midpoint
from .pwma import pwma
from .rma import rma
from .sinwma import sinwma
from .sma import sma
from .swma import swma
from .t3 import t3
from .tema import tema
from .trima import trima
from .vidya import vidya
from .wma import wma
from .zlma import zlma


def ma(name:str = None, source:Series = None, **kwargs) -> Series:
    """Simple MA Utility for easier MA selection

    Available MAs:
        dema, ema, fwma, hma, linreg, midpoint, pwma, rma,
        sinwma, sma, swma, t3, tema, trima, vidya, wma, zlma

    Examples:
        ema8 = ta.ma("ema", df.close, length=8)
        sma50 = ta.ma("sma", df.close, length=50)
        pwma10 = ta.ma("pwma", df.close, length=10, asc=False)

    Args:
        name (str): One of the Available MAs. Default: "ema"
        source (pd.Series): The 'source' Series.

    Kwargs:
        Any additional kwargs the MA may require.

    Returns:
        pd.Series: New feature generated.
    """

    _mas = [
        "dema", "ema", "fwma", "hma", "linreg", "midpoint", "pwma", "rma",
        "sinwma", "sma", "swma", "t3", "tema", "trima", "vidya", "wma", "zlma"
    ]
    if name is None and source is None:
        return _mas
    elif isinstance(name, str) and name.lower() in _mas:
        name = name.lower()
    else: # "ema"
        name = _mas[1]

    if   name == "dema": return dema(source, **kwargs)
    elif name == "fwma": return fwma(source, **kwargs)
    elif name == "hma": return hma(source, **kwargs)
    elif name == "linreg": return linreg(source, **kwargs)
    elif name == "midpoint": return midpoint(source, **kwargs)
    elif name == "pwma": return pwma(source, **kwargs)
    elif name == "rma": return rma(source, **kwargs)
    elif name == "sinwma": return sinwma(source, **kwargs)
    elif name == "sma": return sma(source, **kwargs)
    elif name == "swma": return swma(source, **kwargs)
    elif name == "t3": return t3(source, **kwargs)
    elif name == "tema": return tema(source, **kwargs)
    elif name == "trima": return trima(source, **kwargs)
    elif name == "vidya": return vidya(source, **kwargs)
    elif name == "wma": return wma(source, **kwargs)
    elif name == "zlma": return zlma(source, **kwargs)
    else: return ema(source, **kwargs)