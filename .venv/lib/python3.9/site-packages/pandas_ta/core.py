# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from multiprocessing import cpu_count, Pool
from pathlib import Path
from time import perf_counter
from typing import List, Tuple
from warnings import simplefilter

import pandas as pd
from numpy import log10 as npLog10
from numpy import ndarray as npNdarray
from pandas.core.base import PandasObject

from pandas_ta import Category, Imports, version
from pandas_ta.candles.cdl_pattern import ALL_PATTERNS
from pandas_ta.candles import *
from pandas_ta.cycles import *
from pandas_ta.momentum import *
from pandas_ta.overlap import *
from pandas_ta.performance import *
from pandas_ta.statistics import *
from pandas_ta.trend import *
from pandas_ta.volatility import *
from pandas_ta.volume import *
from pandas_ta.utils import *


df = pd.DataFrame()

# Strategy DataClass
@dataclass
class Strategy:
    """Strategy DataClass
    A way to name and group your favorite indicators

    Args:
        name (str): Some short memorable string.  Note: Case-insensitive "All" is reserved.
        ta (list of dicts): A list of dicts containing keyword arguments where "kind" is the indicator.
        description (str): A more detailed description of what the Strategy tries to capture. Default: None
        created (str): At datetime string of when it was created. Default: Automatically generated. *Subject to change*

    Example TA:
    ta = [
        {"kind": "sma", "length": 200},
        {"kind": "sma", "close": "volume", "length": 50},
        {"kind": "bbands", "length": 20},
        {"kind": "rsi"},
        {"kind": "macd", "fast": 8, "slow": 21},
        {"kind": "sma", "close": "volume", "length": 20, "prefix": "VOLUME"},
    ]
    """

    name: str  # = None # Required.
    ta: List = field(default_factory=list)  # Required.
    # Helpful. More descriptive version or notes or w/e.
    description: str = "TA Description"
    # Optional. Gets Exchange Time and Local Time execution time
    created: str = get_time(to_string=True)

    def __post_init__(self):
        has_name = True
        is_ta = False
        required_args = ["[X] Strategy requires the following argument(s):"]

        name_is_str = isinstance(self.name, str)
        ta_is_list = isinstance(self.ta, list)

        if self.name is None or not name_is_str:
            required_args.append(' - name. Must be a string. Example: "My TA". Note: "all" is reserved.')
            has_name != has_name

        if self.ta is None:
            self.ta = None
        elif self.ta is not None and ta_is_list and self.total_ta() > 0:
            # Check that all elements of the list are dicts.
            # Does not check if the dicts values are valid indicator kwargs
            # User must check indicator documentation for all indicators args.
            is_ta = all([isinstance(_, dict) and len(_.keys()) > 0 for _ in self.ta])
        else:
            s = " - ta. Format is a list of dicts. Example: [{'kind': 'sma', 'length': 10}]"
            s += "\n       Check the indicator for the correct arguments if you receive this error."
            required_args.append(s)

        if len(required_args) > 1:
            [print(_) for _ in required_args]
            return None

    def total_ta(self):
        return len(self.ta) if self.ta is not None else 0


# All Default Strategy
AllStrategy = Strategy(
    name="All",
    description="All the indicators with their default settings. Pandas TA default.",
    ta=None,
)

# Default (Example) Strategy.
CommonStrategy = Strategy(
    name="Common Price and Volume SMAs",
    description="Common Price SMAs: 10, 20, 50, 200 and Volume SMA: 20.",
    ta=[
        {"kind": "sma", "length": 10},
        {"kind": "sma", "length": 20},
        {"kind": "sma", "length": 50},
        {"kind": "sma", "length": 200},
        {"kind": "sma", "close": "volume", "length": 20, "prefix": "VOL"}
    ]
)


# Base Class for extending a Pandas DataFrame
class BasePandasObject(PandasObject):
    """Simple PandasObject Extension

    Ensures the DataFrame is not empty and has columns.
    It would be a sad Panda otherwise.

    Args:
        df (pd.DataFrame): Extends Pandas DataFrame
    """

    def __init__(self, df, **kwargs):
        if df.empty: return
        if len(df.columns) > 0:
            common_names = {
                "Date": "date",
                "Time": "time",
                "Timestamp": "timestamp",
                "Datetime": "datetime",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
                "Dividends": "dividends",
                "Stock Splits": "split",
            }
            # Preemptively drop the rows that are all NaNs
            # Might need to be moved to AnalysisIndicators.__call__() to be
            #   toggleable via kwargs.
            # df.dropna(axis=0, inplace=True)
            # Preemptively rename columns to lowercase
            df.rename(columns=common_names, errors="ignore", inplace=True)

            # Preemptively lowercase the index
            index_name = df.index.name
            if index_name is not None:
                df.index.rename(index_name.lower(), inplace=True)

            self._df = df
        else:
            raise AttributeError(f"[X] No columns!")

    def __call__(self, kind, *args, **kwargs):
        raise NotImplementedError()


# Pandas TA - DataFrame Analysis Indicators
@pd.api.extensions.register_dataframe_accessor("ta")
class AnalysisIndicators(BasePandasObject):
    """
    This Pandas Extension is named 'ta' for Technical Analysis. In other words,
    it is a Numerical Time Series Feature Generator where the Time Series data
    is biased towards Financial Market data; typical data includes columns
    named :"open", "high", "low", "close", "volume".

    This TA Library hopefully allows you to apply familiar and unique Technical
    Analysis Indicators easily with the DataFrame Extension named 'ta'. Even
    though 'ta' is a Pandas DataFrame Extension, you can still call Technical
    Analysis indicators individually if you are more comfortable with that
    approach or it allows you to easily and automatically apply the indicators
    with the strategy method. See: help(ta.strategy).

    By default, the 'ta' extension uses lower case column names: open, high,
    low, close, and volume. You can override the defaults by providing the it's
    replacement name when calling the indicator. For example, to call the
    indicator hl2().

    With 'default' columns: open, high, low, close, and volume.
    >>> df.ta.hl2()
    >>> df.ta(kind="hl2")

    With DataFrame columns: Open, High, Low, Close, and Volume.
    >>> df.ta.hl2(high="High", low="Low")
    >>> df.ta(kind="hl2", high="High", low="Low")

    If you do not want to use a DataFrame Extension, just call it normally.
    >>> sma10 = ta.sma(df["Close"]) # Default length=10
    >>> sma50 = ta.sma(df["Close"], length=50)
    >>> ichimoku, span = ta.ichimoku(df["High"], df["Low"], df["Close"])

    Args:
        kind (str, optional): Default: None. Kind is the 'name' of the indicator.
            It converts kind to lowercase before calling.
        timed (bool, optional): Default: False. Curious about the execution
            speed?
        kwargs: Extension specific modifiers.
            append (bool, optional): Default: False. When True, it appends the
            resultant column(s) to the DataFrame.

    Returns:
        Most Indicators will return a Pandas Series. Others like MACD, BBANDS,
        KC, et al will return a Pandas DataFrame. Ichimoku on the other hand
        will return two DataFrames, the Ichimoku DataFrame for the known period
        and a Span DataFrame for the future of the Span values.

    Let's get started!

    1. Loading the 'ta' module:
    >>> import pandas as pd
    >>> import ta as ta

    2. Load some data:
    >>> df = pd.read_csv("AAPL.csv", index_col="date", parse_dates=True)

    3. Help!
    3a. General Help:
    >>> help(df.ta)
    >>> df.ta()
    3b. Indicator Help:
    >>> help(ta.apo)
    3c. Indicator Extension Help:
    >>> help(df.ta.apo)

    4. Ways of calling an indicator.
    4a. Standard: Calling just the APO indicator without "ta" DataFrame extension.
    >>> ta.apo(df["close"])
    4b. DataFrame Extension: Calling just the APO indicator with "ta" DataFrame extension.
    >>> df.ta.apo()
    4c. DataFrame Extension (kind): Calling APO using 'kind'
    >>> df.ta(kind="apo")
    4d. Strategy:
    >>> df.ta.strategy("All") # Default
    >>> df.ta.strategy(ta.Strategy("My Strat", ta=[{"kind": "apo"}])) # Custom

    5. Working with kwargs
    5a. Append the result to the working df.
    >>> df.ta.apo(append=True)
    5b. Timing an indicator.
    >>> apo = df.ta(kind="apo", timed=True)
    >>> print(apo.timed)
    """

    _adjusted = None
    _cores = cpu_count()
    _df = DataFrame()
    _exchange = "NYSE"
    _time_range = "years"
    _last_run = get_time(_exchange, to_string=True)

    def __init__(self, pandas_obj):
        self._validate(pandas_obj)
        self._df = pandas_obj
        self._last_run = get_time(self._exchange, to_string=True)

    @staticmethod
    def _validate(obj: Tuple[pd.DataFrame, pd.Series]):
        if not isinstance(obj, pd.DataFrame) and not isinstance(obj, pd.Series):
            raise AttributeError("[X] Must be either a Pandas Series or DataFrame.")

    # DataFrame Behavioral Methods
    def __call__(
            self, kind: str = None,
            timed: bool = False, version: bool = False, **kwargs
        ):
        if version: print(f"Pandas TA - Technical Analysis Indicators - v{self.version}")
        try:
            if isinstance(kind, str):
                kind = kind.lower()
                fn = getattr(self, kind)

                if timed:
                    stime = perf_counter()

                # Run the indicator
                result = fn(**kwargs)  # = getattr(self, kind)(**kwargs)
                self._last_run = get_time(self.exchange, to_string=True) # Save when it completed it's run

                if timed:
                    result.timed = final_time(stime)
                    print(f"[+] {kind}: {result.timed}")

                return result
            else:
                self.help()

        except BaseException:
            pass

    # Public Get/Set DataFrame Properties
    @property
    def adjusted(self) -> str:
        """property: df.ta.adjusted"""
        return self._adjusted

    @adjusted.setter
    def adjusted(self, value: str) -> None:
        """property: df.ta.adjusted = 'adj_close'"""
        if value is not None and isinstance(value, str):
            self._adjusted = value
        else:
            self._adjusted = None

    @property
    def cores(self) -> str:
        """Returns the categories."""
        return self._cores

    @cores.setter
    def cores(self, value: int) -> None:
        """property: df.ta.cores = integer"""
        cpus = cpu_count()
        if value is not None and isinstance(value, int):
            self._cores = int(value) if 0 <= value <= cpus else cpus
        else:
            self._cores = cpus

    @property
    def exchange(self) -> str:
        """Returns the current Exchange. Default: "NYSE"."""
        return self._exchange

    @exchange.setter
    def exchange(self, value: str) -> None:
        """property: df.ta.exchange = "LSE" """
        if value is not None and isinstance(value, str) and value in EXCHANGE_TZ.keys():
            self._exchange = value

    @property
    def last_run(self) -> str:
        """Returns the time when the DataFrame was last run."""
        return self._last_run

    # Public Get DataFrame Properties
    @property
    def categories(self) -> str:
        """Returns the categories."""
        return list(Category.keys())

    @property
    def datetime_ordered(self) -> bool:
        """Returns True if the index is a datetime and ordered."""
        hasdf = hasattr(self, "_df")
        if hasdf:
            return is_datetime_ordered(self._df)
        return hasdf

    @property
    def reverse(self) -> pd.DataFrame:
        """Reverses the DataFrame. Simply: df.iloc[::-1]"""
        return self._df.iloc[::-1]

    @property
    def time_range(self) -> float:
        """Returns the time ranges of the DataFrame as a float. Default is in "years". help(ta.toal_time)"""
        return total_time(self._df, self._time_range)

    @time_range.setter
    def time_range(self, value: str) -> None:
        """property: df.ta.time_range = "years" (Default)"""
        if value is not None and isinstance(value, str):
            self._time_range = value
        else:
            self._time_range = "years"

    @property
    def to_utc(self) -> None:
        """Sets the DataFrame index to UTC format"""
        self._df = to_utc(self._df)

    @property
    def version(self) -> str:
        """Returns the version."""
        return version

    # Private DataFrame Methods
    def _add_prefix_suffix(self, result=None, **kwargs) -> None:
        """Add prefix and/or suffix to the result columns"""
        if result is None:
            return
        else:
            prefix = suffix = ""
            delimiter = kwargs.setdefault("delimiter", "_")

            if "prefix" in kwargs:
                prefix = f"{kwargs['prefix']}{delimiter}"
            if "suffix" in kwargs:
                suffix = f"{delimiter}{kwargs['suffix']}"

            if isinstance(result, pd.Series):
                result.name = prefix + result.name + suffix
            else:
                result.columns = [prefix + column + suffix for column in result.columns]

    def _append(self, result=None, **kwargs) -> None:
        """Appends a Pandas Series or DataFrame columns to self._df."""
        if "append" in kwargs and kwargs["append"]:
            df = self._df
            if df is None or result is None: return
            else:
                simplefilter(action="ignore", category=pd.errors.PerformanceWarning)
                if "col_names" in kwargs and not isinstance(kwargs["col_names"], tuple):
                    kwargs["col_names"] = (kwargs["col_names"],) # Note: tuple(kwargs["col_names"]) doesn't work

                if isinstance(result, pd.DataFrame):
                    # If specified in kwargs, rename the columns.
                    # If not, use the default names.
                    if "col_names" in kwargs and isinstance(kwargs["col_names"], tuple):
                        if len(kwargs["col_names"]) >= len(result.columns):
                            for col, ind_name in zip(result.columns, kwargs["col_names"]):
                                df[ind_name] = result.loc[:, col]
                        else:
                            print(f"Not enough col_names were specified : got {len(kwargs['col_names'])}, expected {len(result.columns)}.")
                            return
                    else:
                        for i, column in enumerate(result.columns):
                            df[column] = result.iloc[:, i]
                else:
                    ind_name = (
                        kwargs["col_names"][0] if "col_names" in kwargs and
                        isinstance(kwargs["col_names"], tuple) else result.name
                    )
                    df[ind_name] = result

    def _check_na_columns(self, stdout: bool = True):
        """Returns the columns in which all it's values are na."""
        return [x for x in self._df.columns if all(self._df[x].isna())]

    def _get_column(self, series):
        """Attempts to get the correct series or 'column' and return it."""
        df = self._df
        if df is None: return

        # Explicitly passing a pd.Series to override default.
        if isinstance(series, pd.Series):
            return series
        # Apply default if no series nor a default.
        elif series is None:
            return df[self.adjusted] if self.adjusted is not None else None
        # Ok.  So it's a str.
        elif isinstance(series, str):
            # Return the df column since it's in there.
            if series in df.columns:
                return df[series]
            else:
                # Attempt to match the 'series' because it was likely
                # misspelled.
                matches = df.columns.str.match(series, case=False)
                match = [i for i, x in enumerate(matches) if x]
                # If found, awesome.  Return it or return the 'series'.
                cols = ", ".join(list(df.columns))
                NOT_FOUND = f"[X] Ooops!!! It's {series not in df.columns}, the series '{series}' was not found in {cols}"
                return df.iloc[:, match[0]] if len(match) else print(NOT_FOUND)

    def _indicators_by_category(self, name: str) -> list:
        """Returns indicators by Categorical name."""
        return Category[name] if name in self.categories else None

    def _mp_worker(self, arguments: tuple):
        """Multiprocessing Worker to handle different Methods."""
        method, args, kwargs = arguments

        if method != "ichimoku":
            return getattr(self, method)(*args, **kwargs)
        else:
            return getattr(self, method)(*args, **kwargs)[0]

    def _post_process(self, result, **kwargs) -> Tuple[pd.Series, pd.DataFrame]:
        """Applies any additional modifications to the DataFrame
        * Applies prefixes and/or suffixes
        * Appends the result to main DataFrame
        """
        verbose = kwargs.pop("verbose", False)
        if not isinstance(result, (pd.Series, pd.DataFrame)):
            if verbose:
                print(f"[X] Oops! The result was not a Series or DataFrame.")
            return self._df
        else:
            # Append only specific columns to the dataframe (via
            # 'col_numbers':(0,1,3) for example)
            result = (result.iloc[:, [int(n) for n in kwargs["col_numbers"]]]
                      if isinstance(result, pd.DataFrame) and
                      "col_numbers" in kwargs and
                      kwargs["col_numbers"] is not None else result)
            # Add prefix/suffix and append to the dataframe
            self._add_prefix_suffix(result=result, **kwargs)
            self._append(result=result, **kwargs)
        return result

    def _strategy_mode(self, *args) -> tuple:
        """Helper method to determine the mode and name of the strategy. Returns tuple: (name:str, mode:dict)"""
        name = "All"
        mode = {"all": False, "category": False, "custom": False}

        if len(args) == 0:
            mode["all"] = True
        else:
            if isinstance(args[0], str):
                if args[0].lower() == "all":
                    name, mode["all"] = name, True
                if args[0].lower() in self.categories:
                    name, mode["category"] = args[0], True

            if isinstance(args[0], Strategy):
                strategy_ = args[0]
                if strategy_.ta is None or strategy_.name.lower() == "all":
                    name, mode["all"] = name, True
                elif strategy_.name.lower() in self.categories:
                    name, mode["category"] = strategy_.name, True
                else:
                    name, mode["custom"] = strategy_.name, True

        return name, mode

    # Public DataFrame Methods
    def constants(self, append: bool, values: list):
        """Constants

        Add or remove constants to the DataFrame easily with Numpy's arrays or
        lists. Useful when you need easily accessible horizontal lines for
        charting.

        Add constant '1' to the DataFrame
        >>> df.ta.constants(True, [1])
        Remove constant '1' to the DataFrame
        >>> df.ta.constants(False, [1])

        Adding constants for charting
        >>> import numpy as np
        >>> chart_lines = np.append(np.arange(-4, 5, 1), np.arange(-100, 110, 10))
        >>> df.ta.constants(True, chart_lines)
        Removing some constants from the DataFrame
        >>> df.ta.constants(False, np.array([-60, -40, 40, 60]))

        Args:
            append (bool): If True, appends a Numpy range of constants to the
                working DataFrame.  If False, it removes the constant range from
                the working DataFrame. Default: None.

        Returns:
            Returns the appended constants
            Returns nothing to the user.  Either adds or removes constant ranges
            from the working DataFrame.
        """
        if isinstance(values, npNdarray) or isinstance(values, list):
            if append:
                for x in values:
                    self._df[f"{x}"] = x
                return self._df[self._df.columns[-len(values):]]
            else:
                for x in values:
                    del self._df[f"{x}"]

    def indicators(self, **kwargs):
        """List of Indicators

        kwargs:
            as_list (bool, optional): When True, it returns a list of the
                indicators. Default: False.
            exclude (list, optional): The passed in list will be excluded
                from the indicators list. Default: None.

        Returns:
            Prints the list of indicators. If as_list=True, then a list.
        """
        as_list = kwargs.setdefault("as_list", False)
        # Public non-indicator methods
        helper_methods = ["constants", "indicators", "strategy"]
        # Public df.ta.properties
        ta_properties = [
            "adjusted",
            "categories",
            "cores",
            "datetime_ordered",
            "exchange",
            "last_run",
            "reverse",
            "ticker",
            "time_range",
            "to_utc",
            "version",
        ]

        # Public non-indicator methods
        ta_indicators = list((x for x in dir(pd.DataFrame().ta) if not x.startswith("_") and not x.endswith("_")))

        # Add Pandas TA methods and properties to be removed
        removed = helper_methods + ta_properties

        # Add user excluded methods to be removed
        user_excluded = kwargs.setdefault("exclude", [])
        if isinstance(user_excluded, list) and len(user_excluded) > 0:
            removed += user_excluded

        # Remove the unwanted indicators
        [ta_indicators.remove(x) for x in removed]

        # If as a list, immediately return
        if as_list:
            return ta_indicators

        total_indicators = len(ta_indicators)
        header = f"Pandas TA - Technical Analysis Indicators - v{self.version}"
        s = f"{header}\nTotal Indicators & Utilities: {total_indicators + len(ALL_PATTERNS)}\n"
        if total_indicators > 0:
            print(f"{s}Abbreviations:\n    {', '.join(ta_indicators)}\n\nCandle Patterns:\n    {', '.join(ALL_PATTERNS)}")
        else:
            print(s)

    def strategy(self, *args, **kwargs):
        """Strategy Method

        An experimental method that by default runs all applicable indicators.
        Future implementations will allow more specific indicator generation
        with possibly as json, yaml config file or an sqlite3 table.


        Kwargs:
            chunksize (bool): Adjust the chunksize for the Multiprocessing Pool.
                Default: Number of cores of the OS
            exclude (list): List of indicator names to exclude. Some are
                excluded by default for various reasons; they require additional
                sources, performance (td_seq), not a ohlcv chart (vp) etc.
            name (str): Select all indicators or indicators by
                Category such as: "candles", "cycles", "momentum", "overlap",
                "performance", "statistics", "trend", "volatility", "volume", or
                "all". Default: "all"
            ordered (bool): Whether to run "all" in order. Default: True
            timed (bool): Show the process time of the strategy().
                Default: False
            verbose (bool): Provide some additional insight on the progress of
                the strategy() execution. Default: False
        """
        # If True, it returns the resultant DataFrame. Default: False
        returns = kwargs.pop("returns", False)
        # cpus = cpu_count()
        # Ensure indicators are appended to the DataFrame
        kwargs["append"] = True
        all_ordered = kwargs.pop("ordered", True)
        mp_chunksize = kwargs.pop("chunksize", self.cores)

        # Initialize
        initial_column_count = len(self._df.columns)
        excluded = [
            "above",
            "above_value",
            "below",
            "below_value",
            "cross",
            "cross_value",
            # "data", # reserved
            "long_run",
            "short_run",
            "td_seq", # Performance exclusion
            "tsignals",
            "vp",
            "xsignals",
        ]

        # Get the Strategy Name and mode
        name, mode = self._strategy_mode(*args)

        # If All or a Category, exclude user list if any
        user_excluded = kwargs.pop("exclude", [])
        if mode["all"] or mode["category"]:
            excluded += user_excluded

        # Collect the indicators, remove excluded or include kwarg["append"]
        if mode["category"]:
            ta = self._indicators_by_category(name.lower())
            [ta.remove(x) for x in excluded if x in ta]
        elif mode["custom"]:
            ta = args[0].ta
            for kwds in ta:
                kwds["append"] = True
        elif mode["all"]:
            ta = self.indicators(as_list=True, exclude=excluded)
        else:
            print(f"[X] Not an available strategy.")
            return None

        # Remove Custom indicators with "length" keyword when larger than the DataFrame
        # Possible to have other indicator main window lengths to be included
        removal = []
        for kwds in ta:
            _ = False
            if "length" in kwds and kwds["length"] > self._df.shape[0]: _ = True
            if _: removal.append(kwds)
        if len(removal) > 0: [ta.remove(x) for x in removal]

        verbose = kwargs.pop("verbose", False)
        if verbose:
            print(f"[+] Strategy: {name}\n[i] Indicator arguments: {kwargs}")
            if mode["all"] or mode["category"]:
                excluded_str = ", ".join(excluded)
                print(f"[i] Excluded[{len(excluded)}]: {excluded_str}")

        timed = kwargs.pop("timed", False)
        results = []
        use_multiprocessing = True if self.cores > 0 else False
        has_col_names = False

        if timed:
            stime = perf_counter()

        if use_multiprocessing and mode["custom"]:
            # Determine if the Custom Model has 'col_names' parameter
            has_col_names = (True if len([
                True for x in ta
                if "col_names" in x and isinstance(x["col_names"], tuple)
            ]) else False)

            if has_col_names:
                use_multiprocessing = False

        if Imports["tqdm"]:
            # from tqdm import tqdm
            from tqdm import tqdm

        if use_multiprocessing:
            _total_ta = len(ta)
            with Pool(self.cores) as pool:
                # Some magic to optimize chunksize for speed based on total ta indicators
                _chunksize = mp_chunksize - 1 if mp_chunksize > _total_ta else int(npLog10(_total_ta)) + 1
                if verbose:
                    print(f"[i] Multiprocessing {_total_ta} indicators with {_chunksize} chunks and {self.cores}/{cpu_count()} cpus.")

                results = None
                if mode["custom"]:
                    # Create a list of all the custom indicators into a list
                    custom_ta = [(
                        ind["kind"],
                        ind["params"] if "params" in ind and isinstance(ind["params"], tuple) else (),
                        {**ind, **kwargs},
                    ) for ind in ta]
                    # Custom multiprocessing pool. Must be ordered for Chained Strategies
                    # May fix this to cpus if Chaining/Composition if it remains
                    results = pool.imap(self._mp_worker, custom_ta, _chunksize)
                else:
                    default_ta = [(ind, tuple(), kwargs) for ind in ta]
                    # All and Categorical multiprocessing pool.
                    if all_ordered:
                        if Imports["tqdm"]:
                            results = tqdm(pool.imap(self._mp_worker, default_ta, _chunksize)) # Order over Speed
                        else:
                            results = pool.imap(self._mp_worker, default_ta, _chunksize) # Order over Speed
                    else:
                        if Imports["tqdm"]:
                            results = tqdm(pool.imap_unordered(self._mp_worker, default_ta, _chunksize)) # Speed over Order
                        else:
                            results = pool.imap_unordered(self._mp_worker, default_ta, _chunksize) # Speed over Order
                if results is None:
                    print(f"[X] ta.strategy('{name}') has no results.")
                    return

                pool.close()
                pool.join()
                self._last_run = get_time(self.exchange, to_string=True)

        else:
            # Without multiprocessing:
            if verbose:
                _col_msg = f"[i] No mulitproccessing (cores = 0)."
                if has_col_names:
                    _col_msg = f"[i] No mulitproccessing support for 'col_names' option."
                print(_col_msg)

            if mode["custom"]:
                if Imports["tqdm"] and verbose:
                    pbar = tqdm(ta, f"[i] Progress")
                    for ind in pbar:
                        params = ind["params"] if "params" in ind and isinstance(ind["params"], tuple) else tuple()
                        getattr(self, ind["kind"])(*params, **{**ind, **kwargs})
                else:
                    for ind in ta:
                        params = ind["params"] if "params" in ind and isinstance(ind["params"], tuple) else tuple()
                        getattr(self, ind["kind"])(*params, **{**ind, **kwargs})
            else:
                if Imports["tqdm"] and verbose:
                    pbar = tqdm(ta, f"[i] Progress")
                    for ind in pbar:
                        getattr(self, ind)(*tuple(), **kwargs)
                else:
                    for ind in ta:
                        getattr(self, ind)(*tuple(), **kwargs)
                self._last_run = get_time(self.exchange, to_string=True)

        # Apply prefixes/suffixes and appends indicator results to the  DataFrame
        [self._post_process(r, **kwargs) for r in results]

        if verbose:
            print(f"[i] Total indicators: {len(ta)}")
            print(f"[i] Columns added: {len(self._df.columns) - initial_column_count}")
            print(f"[i] Last Run: {self._last_run}")
        if timed:
            print(f"[i] Runtime: {final_time(stime)}")

        if returns: return self._df


    def ticker(self, ticker: str, **kwargs):
        """ticker

        This method downloads Historical Data if the package yfinance is installed.
        Additionally it can run a ta.Strategy; Builtin or Custom. It returns a
        DataFrame if there the DataFrame is not empty, otherwise it exits. For
        additional yfinance arguments, use help(ta.yf).

        Historical Data
        >>> df = df.ta.ticker("aapl")
        More specifically
        >>> df = df.ta.ticker("aapl", period="max", interval="1d", kind=None)

        Changing the period of Historical Data
        Period is used instead of start/end
        >>> df = df.ta.ticker("aapl", period="1y")

        Changing the period and interval of Historical Data
        Retrieves the past year in weeks
        >>> df = df.ta.ticker("aapl", period="1y", interval="1wk")
        Retrieves the past month in hours
        >>> df = df.ta.ticker("aapl", period="1mo", interval="1h")

        Show everything
        >>> df = df.ta.ticker("aapl", kind="all")

        Args:
            ticker (str): Any string for a ticker you would use with yfinance.
                Default: "SPY"
        Kwargs:
            kind (str): Options see above. Default: "history"
            ds (str): Data Source to use. Default: "yahoo"
            strategy (str | ta.Strategy): Which strategy to apply after
                downloading chart history. Default: None

            See help(ta.yf) for additional kwargs

        Returns:
            Exits if the DataFrame is empty or None
            Otherwise it returns a DataFrame
        """
        ds = kwargs.pop("ds", "yahoo")
        strategy = kwargs.pop("strategy", None)

        # Fetch the Data
        ds = ds.lower() is not None and isinstance(ds, str)
        # df = av(ticker, **kwargs) if ds and ds == "av" else yf(ticker, **kwargs)
        df = yf(ticker, **kwargs)

        if df is None: return
        elif df.empty:
            print(f"[X] DataFrame is empty: {df.shape}")
            return
        else:
            if kwargs.pop("lc_cols", False):
                df.index.name = df.index.name.lower()
                df.columns = df.columns.str.lower()
            self._df = df

        if strategy is not None: self.strategy(strategy, **kwargs)
        return df


    # Public DataFrame Methods: Indicators and Utilities
    # Candles
    def cdl_pattern(self, name="all", offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = cdl_pattern(open_=open_, high=high, low=low, close=close, name=name, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cdl_z(self, full=None, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = cdl_z(open_=open_, high=high, low=low, close=close, full=full, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ha(self, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = ha(open_=open_, high=high, low=low, close=close, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Cycles
    def ebsw(self, close=None, length=None, bars=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = ebsw(close=close, length=length, bars=bars, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Momentum
    def ao(self, fast=None, slow=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = ao(high=high, low=low, fast=fast, slow=slow, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def apo(self, fast=None, slow=None, mamode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = apo(close=close, fast=fast, slow=slow, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def bias(self, length=None, mamode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = bias(close=close, length=length, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def bop(self, percentage=False, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = bop(open_=open_, high=high, low=low, close=close, percentage=percentage, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def brar(self, length=None, scalar=None, drift=None, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = brar(open_=open_, high=high, low=low, close=close, length=length, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cci(self, length=None, c=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = cci(high=high, low=low, close=close, length=length, c=c, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cfo(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = cfo(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cg(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = cg(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cmo(self, length=None, scalar=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = cmo(close=close, length=length, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def coppock(self, length=None, fast=None, slow=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = coppock(close=close, length=length, fast=fast, slow=slow, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cti(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = cti(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def dm(self, drift=None, offset=None, mamode=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = dm(high=high, low=low, drift=drift, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def er(self, length=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = er(close=close, length=length, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def eri(self, length=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = eri(high=high, low=low, close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def fisher(self, length=None, signal=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = fisher(high=high, low=low, length=length, signal=signal, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def inertia(self, length=None, rvi_length=None, scalar=None, refined=None, thirds=None, mamode=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        if refined is not None or thirds is not None:
            high = self._get_column(kwargs.pop("high", "high"))
            low = self._get_column(kwargs.pop("low", "low"))
            result = inertia(close=close, high=high, low=low, length=length, rvi_length=rvi_length, scalar=scalar, refined=refined, thirds=thirds, mamode=mamode, drift=drift, offset=offset, **kwargs)
        else:
            result = inertia(close=close, length=length, rvi_length=rvi_length, scalar=scalar, refined=refined, thirds=thirds, mamode=mamode, drift=drift, offset=offset, **kwargs)

        return self._post_process(result, **kwargs)

    def kdj(self, length=None, signal=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = kdj(high=high, low=low, close=close, length=length, signal=signal, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def kst(self, roc1=None, roc2=None, roc3=None, roc4=None, sma1=None, sma2=None, sma3=None, sma4=None, signal=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = kst(close=close, roc1=roc1, roc2=roc2, roc3=roc3, roc4=roc4, sma1=sma1, sma2=sma2, sma3=sma3, sma4=sma4, signal=signal, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def macd(self, fast=None, slow=None, signal=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = macd(close=close, fast=fast, slow=slow, signal=signal, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def mom(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = mom(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pgo(self, length=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = pgo(high=high, low=low, close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ppo(self, fast=None, slow=None, scalar=None, mamode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = ppo(close=close, fast=fast, slow=slow, scalar=scalar, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def psl(self, open_=None, length=None, scalar=None, drift=None, offset=None, **kwargs):
        if open_ is not None:
            open_ = self._get_column(kwargs.pop("open", "open"))

        close = self._get_column(kwargs.pop("close", "close"))
        result = psl(close=close, open_=open_, length=length, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pvo(self, fast=None, slow=None, signal=None, scalar=None, offset=None, **kwargs):
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = pvo(volume=volume, fast=fast, slow=slow, signal=signal, scalar=scalar, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def qqe(self, length=None, smooth=None, factor=None, mamode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = qqe(close=close, length=length, smooth=smooth, factor=factor, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def roc(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = roc(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def rsi(self, length=None, scalar=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = rsi(close=close, length=length, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def rsx(self, length=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = rsx(close=close, length=length, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def rvgi(self, length=None, swma_length=None, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = rvgi(open_=open_, high=high, low=low, close=close, length=length, swma_length=swma_length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def slope(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = slope(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def smi(self, fast=None, slow=None, signal=None, scalar=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = smi(close=close, fast=fast, slow=slow, signal=signal, scalar=scalar, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def squeeze(self, bb_length=None, bb_std=None, kc_length=None, kc_scalar=None, mom_length=None, mom_smooth=None, use_tr=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = squeeze(high=high, low=low, close=close, bb_length=bb_length, bb_std=bb_std, kc_length=kc_length, kc_scalar=kc_scalar, mom_length=mom_length, mom_smooth=mom_smooth, use_tr=use_tr, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def squeeze_pro(self, bb_length=None, bb_std=None, kc_length=None, kc_scalar_wide=None, kc_scalar_normal=None, kc_scalar_narrow=None, mom_length=None, mom_smooth=None, use_tr=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = squeeze_pro(high=high, low=low, close=close, bb_length=bb_length, bb_std=bb_std, kc_length=kc_length, kc_scalar_wide=kc_scalar_wide, kc_scalar_normal=kc_scalar_normal, kc_scalar_narrow=kc_scalar_narrow, mom_length=mom_length, mom_smooth=mom_smooth, use_tr=use_tr, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def stc(self, ma1=None, ma2=None, osc=None, tclength=None, fast=None, slow=None, factor=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = stc(close=close, ma1=ma1, ma2=ma2, osc=osc, tclength=tclength, fast=fast, slow=slow, factor=factor, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def stoch(self, fast_k=None, slow_k=None, slow_d=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = stoch(high=high, low=low, close=close, fast_k=fast_k, slow_k=slow_k, slow_d=slow_d, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def stochrsi(self, length=None, rsi_length=None, k=None, d=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = stochrsi(high=high, low=low, close=close, length=length, rsi_length=rsi_length, k=k, d=d, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def td_seq(self, asint=None, offset=None, show_all=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = td_seq(close=close, asint=asint, offset=offset, show_all=show_all, **kwargs)
        return self._post_process(result, **kwargs)

    def trix(self, length=None, signal=None, scalar=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = trix(close=close, length=length, signal=signal, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def tsi(self, fast=None, slow=None, drift=None, mamode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = tsi(close=close, fast=fast, slow=slow, drift=drift, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def uo(self, fast=None, medium=None, slow=None, fast_w=None, medium_w=None, slow_w=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = uo(high=high, low=low, close=close, fast=fast, medium=medium, slow=slow, fast_w=fast_w, medium_w=medium_w, slow_w=slow_w, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def willr(self, length=None, percentage=True, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = willr(high=high, low=low, close=close, length=length, percentage=percentage, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Overlap
    def alma(self, length=None, sigma=None, distribution_offset=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = alma(close=close, length=length, sigma=sigma, distribution_offset=distribution_offset, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def dema(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = dema(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ema(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = ema(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def fwma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = fwma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def hilo(self, high_length=None, low_length=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = hilo(high=high, low=low, close=close, high_length=high_length, low_length=low_length, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def hl2(self, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = hl2(high=high, low=low, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def hlc3(self, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = hlc3(high=high, low=low, close=close, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def hma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = hma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def hwma(self, na=None, nb=None, nc=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = hwma(close=close, na=na, nb=nb, nc=nc, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def jma(self, length=None, phase=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = jma(close=close, length=length, phase=phase, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def kama(self, length=None, fast=None, slow=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = kama(close=close, length=length, fast=fast, slow=slow, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ichimoku(self, tenkan=None, kijun=None, senkou=None, include_chikou=True, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result, span = ichimoku(high=high, low=low, close=close, tenkan=tenkan, kijun=kijun, senkou=senkou, include_chikou=include_chikou, offset=offset, **kwargs)
        self._add_prefix_suffix(result, **kwargs)
        self._add_prefix_suffix(span, **kwargs)
        self._append(result, **kwargs)
        # return self._post_process(result, **kwargs), span
        return result, span

    def linreg(self, length=None, offset=None, adjust=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = linreg(close=close, length=length, offset=offset, adjust=adjust, **kwargs)
        return self._post_process(result, **kwargs)

    def mcgd(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = mcgd(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def midpoint(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = midpoint(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def midprice(self, length=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = midprice(high=high, low=low, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ohlc4(self, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = ohlc4(open_=open_, high=high, low=low, close=close, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pwma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = pwma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def rma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = rma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def sinwma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = sinwma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def sma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = sma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ssf(self, length=None, poles=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = ssf(close=close, length=length, poles=poles, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def supertrend(self, length=None, multiplier=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = supertrend(high=high, low=low, close=close, length=length, multiplier=multiplier, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def swma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = swma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def t3(self, length=None, a=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = t3(close=close, length=length, a=a, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def tema(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = tema(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def trima(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = trima(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def vidya(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = vidya(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def vwap(self, anchor=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))

        if not self.datetime_ordered:
            volume.index = self._df.index

        result = vwap(high=high, low=low, close=close, volume=volume, anchor=anchor, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def vwma(self, volume=None, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = vwma(close=close, volume=volume, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def wcp(self, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = wcp(high=high, low=low, close=close, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def wma(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = wma(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def zlma(self, length=None, mamode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = zlma(close=close, length=length, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Performance
    def log_return(self, length=None, cumulative=False, percent=False, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = log_return(close=close, length=length, cumulative=cumulative, percent=percent, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def percent_return(self, length=None, cumulative=False, percent=False, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = percent_return(close=close, length=length, cumulative=cumulative, percent=percent, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Statistics
    def entropy(self, length=None, base=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = entropy(close=close, length=length, base=base, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def kurtosis(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = kurtosis(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def mad(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = mad(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def median(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = median(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def quantile(self, length=None, q=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = quantile(close=close, length=length, q=q, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def skew(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = skew(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def stdev(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = stdev(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def tos_stdevall(self, length=None, stds=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = tos_stdevall(close=close, length=length, stds=stds, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def variance(self, length=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = variance(close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def zscore(self, length=None, std=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = zscore(close=close, length=length, std=std, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Trend
    def adx(self, length=None, lensig=None, mamode=None, scalar=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = adx(high=high, low=low, close=close, length=length, lensig=lensig, mamode=mamode, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def amat(self, fast=None, slow=None, mamode=None, lookback=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = amat(close=close, fast=fast, slow=slow, mamode=mamode, lookback=lookback, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def aroon(self, length=None, scalar=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = aroon(high=high, low=low, length=length, scalar=scalar, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def chop(self, length=None, atr_length=None, scalar=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = chop(high=high, low=low, close=close, length=length, atr_length=atr_length, scalar=scalar, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cksp(self, p=None, x=None, q=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = cksp(high=high, low=low, close=close, p=p, x=x, q=q, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def decay(self, length=None, mode=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = decay(close=close, length=length, mode=mode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def decreasing(self, length=None, strict=None, asint=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = decreasing(close=close, length=length, strict=strict, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def dpo(self, length=None, centered=True, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = dpo(close=close, length=length, centered=centered, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def increasing(self, length=None, strict=None, asint=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = increasing(close=close, length=length, strict=strict, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def long_run(self, fast=None, slow=None, length=None, offset=None, **kwargs):
        if fast is None and slow is None:
            return self._df
        else:
            result = long_run(fast=fast, slow=slow, length=length, offset=offset, **kwargs)
            return self._post_process(result, **kwargs)

    def psar(self, af0=None, af=None, max_af=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", None))
        result = psar(high=high, low=low, close=close, af0=af0, af=af, max_af=max_af, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def qstick(self, length=None, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = qstick(open_=open_, close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def short_run(self, fast=None, slow=None, length=None, offset=None, **kwargs):
        if fast is None and slow is None:
            return self._df
        else:
            result = short_run(fast=fast, slow=slow, length=length, offset=offset, **kwargs)
            return self._post_process(result, **kwargs)

    def supertrend(self, period=None, multiplier=None, mamode=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = supertrend(high=high, low=low, close=close, period=period, multiplier=multiplier, mamode=mamode, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def tsignals(self, trend=None, asbool=None, trend_reset=None, trend_offset=None, offset=None, **kwargs):
        if trend is None:
            return self._df
        else:
            result = tsignals(trend, asbool=asbool, trend_offset=trend_offset, trend_reset=trend_reset, offset=offset, **kwargs)
            return self._post_process(result, **kwargs)

    def ttm_trend(self, length=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = ttm_trend(high=high, low=low, close=close, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def vhf(self, length=None, drift=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = vhf(close=close, length=length, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def vortex(self, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = vortex(high=high, low=low, close=close, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def xsignals(self, signal=None, xa=None, xb=None, above=None, long=None, asbool=None, trend_reset=None, trend_offset=None, offset=None, **kwargs):
        if signal is None:
            return self._df
        else:
            result = xsignals(signal=signal, xa=xa, xb=xb, above=above, long=long, asbool=asbool, trend_offset=trend_offset, trend_reset=trend_reset, offset=offset, **kwargs)
            return self._post_process(result, **kwargs)

    # Utility
    def above(self, asint=True, offset=None, **kwargs):
        a = self._get_column(kwargs.pop("close", "a"))
        b = self._get_column(kwargs.pop("close", "b"))
        result = above(series_a=a, series_b=b, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def above_value(self, value=None, asint=True, offset=None, **kwargs):
        a = self._get_column(kwargs.pop("close", "a"))
        result = above_value(series_a=a, value=value, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def below(self, asint=True, offset=None, **kwargs):
        a = self._get_column(kwargs.pop("close", "a"))
        b = self._get_column(kwargs.pop("close", "b"))
        result = below(series_a=a, series_b=b, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def below_value(self, value=None, asint=True, offset=None, **kwargs):
        a = self._get_column(kwargs.pop("close", "a"))
        result = below_value(series_a=a, value=value, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cross(self, above=True, asint=True, offset=None, **kwargs):
        a = self._get_column(kwargs.pop("close", "a"))
        b = self._get_column(kwargs.pop("close", "b"))
        result = cross(series_a=a, series_b=b, above=above, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cross_value(self, value=None, above=True, asint=True, offset=None, **kwargs):
        a = self._get_column(kwargs.pop("close", "a"))
        # a = self._get_column(a, f"{a}")
        result = cross_value(series_a=a, value=value, above=above, asint=asint, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Volatility
    def aberration(self, length=None, atr_length=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = aberration(high=high, low=low, close=close, length=length, atr_length=atr_length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def accbands(self, length=None, c=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = accbands(high=high, low=low, close=close, length=length, c=c, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def atr(self, length=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = atr(high=high, low=low, close=close, length=length, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def bbands(self, length=None, std=None, mamode=None, offset=None, **kwargs):
        close  = self._get_column(kwargs.pop("close", "close"))
        result = bbands(close=close, length=length, std=std, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def donchian(self, lower_length=None, upper_length=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = donchian(high=high, low=low, lower_length=lower_length, upper_length=upper_length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def hwc(self, na=None, nb=None, nc=None, nd=None, scalar=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = hwc(close=close, na=na, nb=nb, nc=nc, nd=nd, scalar=scalar, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def kc(self, length=None, scalar=None, mamode=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = kc(high=high, low=low, close=close, length=length, scalar=scalar, mamode=mamode, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def massi(self, fast=None, slow=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = massi(high=high, low=low, fast=fast, slow=slow, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def natr(self, length=None, mamode=None, scalar=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = natr(high=high, low=low, close=close, length=length, mamode=mamode, scalar=scalar, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pdist(self, drift=None, offset=None, **kwargs):
        open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = pdist(open_=open_, high=high, low=low, close=close, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def rvi(self, length=None, scalar=None, refined=None, thirds=None, mamode=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = rvi(high=high, low=low, close=close, length=length, scalar=scalar, refined=refined, thirds=thirds, mamode=mamode, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def thermo(self, long=None, short= None, length=None, mamode=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        result = thermo(high=high, low=low, long=long, short=short, length=length, mamode=mamode, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def true_range(self, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        result = true_range(high=high, low=low, close=close, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def ui(self, length=None, scalar=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        result = ui(close=close, length=length, scalar=scalar, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    # Volume
    def ad(self, open_=None, signed=True, offset=None, **kwargs):
        if open_ is not None:
            open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = ad(high=high, low=low, close=close, volume=volume, open_=open_, signed=signed, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def adosc(self, open_=None, fast=None, slow=None, signed=True, offset=None, **kwargs):
        if open_ is not None:
            open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = adosc(high=high, low=low, close=close, volume=volume, open_=open_, fast=fast, slow=slow, signed=signed, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def aobv(self, fast=None, slow=None, mamode=None, max_lookback=None, min_lookback=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = aobv(close=close, volume=volume, fast=fast, slow=slow, mamode=mamode, max_lookback=max_lookback, min_lookback=min_lookback, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def cmf(self, open_=None, length=None, offset=None, **kwargs):
        if open_ is not None:
            open_ = self._get_column(kwargs.pop("open", "open"))
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = cmf(high=high, low=low, close=close, volume=volume, open_=open_, length=length, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def efi(self, length=None, mamode=None, offset=None, drift=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = efi(close=close, volume=volume, length=length, offset=offset, mamode=mamode, drift=drift, **kwargs)
        return self._post_process(result, **kwargs)

    def eom(self, length=None, divisor=None, offset=None, drift=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = eom(high=high, low=low, close=close, volume=volume, length=length, divisor=divisor, offset=offset, drift=drift, **kwargs)
        return self._post_process(result, **kwargs)

    def kvo(self, fast=None, slow=None, length_sig=None, mamode=None, offset=None, drift=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = kvo(high=high, low=low, close=close, volume=volume, fast=fast, slow=slow, length_sig=length_sig, mamode=mamode, offset=offset, drift=drift, **kwargs)
        return self._post_process(result, **kwargs)

    def mfi(self, length=None, drift=None, offset=None, **kwargs):
        high = self._get_column(kwargs.pop("high", "high"))
        low = self._get_column(kwargs.pop("low", "low"))
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = mfi(high=high, low=low, close=close, volume=volume, length=length, drift=drift, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def nvi(self, length=None, initial=None, signed=True, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = nvi(close=close, volume=volume, length=length, initial=initial, signed=signed, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def obv(self, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = obv(close=close, volume=volume, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pvi(self, length=None, initial=None, signed=True, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = pvi(close=close, volume=volume, length=length, initial=initial, signed=signed, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pvol(self, volume=None, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = pvol(close=close, volume=volume, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def pvr(self, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = pvr(close=close, volume=volume)
        return self._post_process(result, **kwargs)

    def pvt(self, offset=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = pvt(close=close, volume=volume, offset=offset, **kwargs)
        return self._post_process(result, **kwargs)

    def vp(self, width=None, percent=None, **kwargs):
        close = self._get_column(kwargs.pop("close", "close"))
        volume = self._get_column(kwargs.pop("volume", "volume"))
        result = vp(close=close, volume=volume, width=width, percent=percent, **kwargs)
        return self._post_process(result, **kwargs)
