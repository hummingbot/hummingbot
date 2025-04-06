# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta import Imports, RATE, version
# from .._core import _camelCase2Title
# from .._time import ytd_df

def av(ticker: str, **kwargs):
    print(f"[!] kwargs: {kwargs}")
    verbose = kwargs.pop("verbose", False)
    kind = kwargs.pop("kind", "history")
    kind = kind.lower()
    interval = kwargs.pop("interval", "D")
    show = kwargs.pop("show", None)
    # last = kwargs.pop("last", RATE["TRADING_DAYS_PER_YEAR"])

    ticker = ticker.upper() if ticker is not None and isinstance(ticker, str) else None

    if Imports["alphaVantage-api"] and ticker is not None:
        # from alphaVantageAPI import alphavantage
        import alphaVantageAPI as AV
        AVC = {"api_key": "YOUR API KEY", "clean": True, "export": False, "output_size": "full", "premium": False}
        _config = kwargs.pop("av_kwargs", AVC)
        av = AV.AlphaVantage(**_config)

        period = kwargs.pop("period", av.output_size)

        _all, div = ["all"], "=" * 53 # Max div width is 80

        if kind in _all or verbose: pass

        if kind in _all + ["history", "h"]:
            if verbose:
                print("\n====  Chart History       " + div + f"\n[*] Pandas TA v{version} & alphaVantage-api")
                print(f"[+] Downloading {ticker}[{interval}:{period}] from {av.API_NAME} (https://www.alphavantage.co/)")
            df = av.data(ticker, interval)
            df.name = ticker
            if show is not None and isinstance(show, int) and show > 0:
                print(f"\n{df.name}\n{df.tail(show)}\n")
            return df

    return DataFrame()
