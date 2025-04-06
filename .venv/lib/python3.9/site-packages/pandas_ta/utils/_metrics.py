# -*- coding: utf-8 -*-
from typing import Tuple

from numpy import log as npLog
from numpy import nan as npNaN
from numpy import sqrt as npSqrt
from pandas import Series, Timedelta

from ._core import verify_series
from ._time import total_time
from ._math import linear_regression, log_geometric_mean
from pandas_ta import RATE
from pandas_ta.performance import drawdown, log_return, percent_return


def cagr(close: Series) -> float:
    """Compounded Annual Growth Rate

    Args:
        close (pd.Series): Series of 'close's

    >>> result = ta.cagr(df.close)
    """
    close = verify_series(close)
    start, end = close.iloc[0], close.iloc[-1]
    return ((end / start) ** (1 / total_time(close))) - 1


def calmar_ratio(close: Series, method: str = "percent", years: int = 3) -> float:
    """The Calmar Ratio is the percent Max Drawdown Ratio 'typically' over
    the past three years.

    Args:
        close (pd.Series): Series of 'close's
        method (str): Max DD calculation options: 'dollar', 'percent', 'log'.
            Default: 'dollar'
        years (int): The positive number of years to use. Default: 3

    >>> result = ta.calmar_ratio(close, method="percent", years=3)
    """
    if years <= 0:
        print(f"[!] calmar_ratio 'years' argument must be greater than zero.")
        return
    close = verify_series(close)

    n_years_ago = close.index[-1] - Timedelta(days=365.25 * years)
    close = close[close.index > n_years_ago]

    return cagr(close) / max_drawdown(close, method=method)


def downside_deviation(returns: Series, benchmark_rate: float = 0.0, tf: str = "years") -> float:
    """Downside Deviation for the Sortino ratio.
    Benchmark rate is assumed to be annualized. Adjusted according for the
    number of periods per year seen in the data.

    Args:
        close (pd.Series): Series of 'close's
        benchmark_rate (float): Benchmark Rate to use. Default: 0.0
        tf (str): Time Frame options: 'days', 'weeks', 'months', and 'years'.
            Default: 'years'

    >>> result = ta.downside_deviation(returns, benchmark_rate=0.0, tf="years")
    """
    # For both de-annualizing the benchmark rate and annualizing result
    returns = verify_series(returns)
    days_per_year = returns.shape[0] / total_time(returns, tf)

    adjusted_benchmark_rate = ((1 + benchmark_rate) ** (1 / days_per_year)) - 1

    downside = adjusted_benchmark_rate - returns
    downside_sum_of_squares = (downside[downside > 0] ** 2).sum()
    downside_deviation = npSqrt(downside_sum_of_squares / (returns.shape[0] - 1))
    return downside_deviation * npSqrt(days_per_year)


def jensens_alpha(returns: Series, benchmark_returns: Series) -> float:
    """Jensen's 'Alpha' of a series and a benchmark.

    Args:
        returns (pd.Series): Series of 'returns's
        benchmark_returns (pd.Series): Series of 'benchmark_returns's

    >>> result = ta.jensens_alpha(returns, benchmark_returns)
    """
    returns = verify_series(returns)
    benchmark_returns = verify_series(benchmark_returns)

    benchmark_returns.interpolate(inplace=True)
    return linear_regression(benchmark_returns, returns)["a"]


def log_max_drawdown(close: Series) -> float:
    """Log Max Drawdown of a series.

    Args:
        close (pd.Series): Series of 'close's

    >>> result = ta.log_max_drawdown(close)
    """
    close = verify_series(close)
    log_return = npLog(close.iloc[-1]) - npLog(close.iloc[0])
    return log_return - max_drawdown(close, method="log")


def max_drawdown(close: Series, method:str = None, all:bool = False) -> float:
    """Maximum Drawdown from close. Default: 'dollar'.

    Args:
        close (pd.Series): Series of 'close's
        method (str): Max DD calculation options: 'dollar', 'percent', 'log'.
            Default: 'dollar'
        all (bool): If True, it returns all three methods as a dict.
            Default: False

    >>> result = ta.max_drawdown(close, method="dollar", all=False)
    """
    close = verify_series(close)
    max_dd = drawdown(close).max()

    max_dd_ = {
        "dollar": max_dd.iloc[0],
        "percent": max_dd.iloc[1],
        "log": max_dd.iloc[2]
    }
    if all: return max_dd_

    if isinstance(method, str) and method in max_dd_.keys():
        return max_dd_[method]
    return max_dd_["dollar"]


def optimal_leverage(
        close: Series, benchmark_rate: float = 0.0,
        period: Tuple[float, int] = RATE["TRADING_DAYS_PER_YEAR"],
        log: bool = False, capital: float = 1., **kwargs
    ) -> float:
    """Optimal Leverage of a series. NOTE: Incomplete. Do NOT use.

    Args:
        close (pd.Series): Series of 'close's
        benchmark_rate (float): Benchmark Rate to use. Default: 0.0
        period (int, float): Period to use to calculate Mean Annual Return and
            Annual Standard Deviation.
            Default: None or the default sharpe_ratio.period()
        log (bool): If True, calculates log_return. Otherwise it returns
            percent_return. Default: False

    >>> result = ta.optimal_leverage(close, benchmark_rate=0.0, log=False)
    """
    close = verify_series(close)

    use_cagr = kwargs.pop("use_cagr", False)
    returns = percent_return(close=close) if not log else log_return(close=close)
    # sharpe = sharpe_ratio(close, benchmark_rate=benchmark_rate, log=log, use_cagr=use_cagr, period=period)

    period_mu = period * returns.mean()
    period_std = npSqrt(period) * returns.std()

    mean_excess_return = period_mu - benchmark_rate
    # sharpe = mean_excess_return / period_std
    opt_leverage = (period_std ** -2) * mean_excess_return

    amount = int(capital * opt_leverage)
    return amount


def pure_profit_score(close: Series) -> Tuple[float, int]:
    """Pure Profit Score of a series.

    Args:
        close (pd.Series): Series of 'close's

    >>> result = ta.pure_profit_score(df.close)
    """
    close = verify_series(close)
    close_index = Series(0, index=close.reset_index().index)

    r = linear_regression(close_index, close)["r"]
    if r is not npNaN:
        return r * cagr(close)
    return 0


def sharpe_ratio(close: Series, benchmark_rate: float = 0.0, log: bool = False, use_cagr: bool = False, period: int = RATE["TRADING_DAYS_PER_YEAR"]) -> float:
    """Sharpe Ratio of a series.

    Args:
        close (pd.Series): Series of 'close's
        benchmark_rate (float): Benchmark Rate to use. Default: 0.0
        log (bool): If True, calculates log_return. Otherwise it returns
            percent_return. Default: False
        use_cagr (bool): Use cagr - benchmark_rate instead. Default: False
        period (int, float): Period to use to calculate Mean Annual Return and
            Annual Standard Deviation.
            Default: RATE["TRADING_DAYS_PER_YEAR"] (currently 252)

    >>> result = ta.sharpe_ratio(close, benchmark_rate=0.0, log=False)
    """
    close = verify_series(close)
    returns = percent_return(close=close) if not log else log_return(close=close)

    if use_cagr:
        return cagr(close) / volatility(close, returns, log=log)
    else:
        period_mu = period * returns.mean()
        period_std = npSqrt(period) * returns.std()
        return (period_mu - benchmark_rate) / period_std


def sortino_ratio(close: Series, benchmark_rate: float = 0.0, log: bool = False) -> float:
    """Sortino Ratio of a series.

    Args:
        close (pd.Series): Series of 'close's
        benchmark_rate (float): Benchmark Rate to use. Default: 0.0
        log (bool): If True, calculates log_return. Otherwise it returns
            percent_return. Default: False

    >>> result = ta.sortino_ratio(close, benchmark_rate=0.0, log=False)
    """
    close = verify_series(close)
    returns = percent_return(close=close) if not log else log_return(close=close)

    result  = cagr(close) - benchmark_rate
    result /= downside_deviation(returns)
    return result


def volatility(close: Series, tf: str = "years", returns: bool = False, log: bool = False, **kwargs) -> float:
    """Volatility of a series. Default: 'years'

    Args:
        close (pd.Series): Series of 'close's
        tf (str): Time Frame options: 'days', 'weeks', 'months', and 'years'.
            Default: 'years'
        returns (bool): If True, then it replace the close Series with the user
            defined Series; typically user generated returns or percent returns
            or log returns. Default: False
        log (bool): If True, calculates log_return. Otherwise it calculates
            percent_return. Default: False

    >>> result = ta.volatility(close, tf="years", returns=False, log=False, **kwargs)
    """
    close = verify_series(close)

    if not returns:
        returns = percent_return(close=close) if not log else log_return(close=close)
    else:
        returns = close

    returns = log_geometric_mean(returns).std()
    # factor = returns.shape[0] / total_time(returns, tf)
    # if kwargs.pop("nearest_day", False) and tf.lower() == "years":
        # factor = int(factor + 1)
    # return npSqrt(factor) * returns.std()
    return returns
