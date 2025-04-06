# -*- coding: utf-8 -*-
from datetime import datetime
from time import localtime, perf_counter
from typing import Tuple

from pandas import DataFrame, Timestamp

from pandas_ta import EXCHANGE_TZ, RATE


def df_dates(df: DataFrame, dates: Tuple[str, list] = None) -> DataFrame:
    """Yields the DataFrame with the given dates"""
    if dates is None: return None
    if not isinstance(dates, list):
        dates = [dates]
    return df[df.index.isin(dates)]


def df_month_to_date(df: DataFrame) -> DataFrame:
    """Yields the Month-to-Date (MTD) DataFrame"""
    in_mtd = df.index >= Timestamp.now().strftime("%Y-%m-01")
    if any(in_mtd): return df[in_mtd]
    return df


def df_quarter_to_date(df: DataFrame) -> DataFrame:
    """Yields the Quarter-to-Date (QTD) DataFrame"""
    now = Timestamp.now()
    for m in [1, 4, 7, 10]:
        if now.month <= m:
                in_qtr = df.index >= datetime(now.year, m, 1).strftime("%Y-%m-01")
                if any(in_qtr): return df[in_qtr]
    return df[df.index >= now.strftime("%Y-%m-01")]


def df_year_to_date(df: DataFrame) -> DataFrame:
    """Yields the Year-to-Date (YTD) DataFrame"""
    in_ytd = df.index >= Timestamp.now().strftime("%Y-01-01")
    if any(in_ytd): return df[in_ytd]
    return df


def final_time(stime: float) -> str:
    """Human readable elapsed time. Calculates the final time elasped since
    stime and returns a string with microseconds and seconds."""
    time_diff = perf_counter() - stime
    return f"{time_diff * 1000:2.4f} ms ({time_diff:2.4f} s)"


def get_time(exchange: str = "NYSE", full:bool = True, to_string:bool = False) -> Tuple[None, str]:
    """Returns Current Time, Day of the Year and Percentage, and the current
    time of the selected Exchange."""
    tz = EXCHANGE_TZ["NYSE"] # Default is NYSE (Eastern Time Zone)
    if isinstance(exchange, str):
        exchange = exchange.upper()
        tz = EXCHANGE_TZ[exchange]

    # today = Timestamp.utcnow()
    today = Timestamp.now()
    date = f"{today.day_name()} {today.month_name()} {today.day}, {today.year}"

    _today = today.timetuple()
    exchange_time = f"{(_today.tm_hour + tz) % 24}:{_today.tm_min:02d}:{_today.tm_sec:02d}"

    if full:
        lt = localtime()
        local_ = f"Local: {lt.tm_hour}:{lt.tm_min:02d}:{lt.tm_sec:02d} {lt.tm_zone}"
        doy = f"Day {today.dayofyear}/365 ({100 * round(today.dayofyear/365, 2):.2f}%)"
        exchange_ = f"{exchange}: {exchange_time}"

        s = f"{date}, {exchange_}, {local_}, {doy}"
    else:
        s = f"{date}, {exchange}: {exchange_time}"

    return s if to_string else print(s)


def total_time(df: DataFrame, tf: str = "years") -> float:
    """Calculates the total time of a DataFrame. Difference of the Last and
    First index. Options: 'months', 'weeks', 'days', 'hours', 'minutes'
    and 'seconds'. Default: 'years'.
    Useful for annualization."""
    time_diff = df.index[-1] - df.index[0]
    TimeFrame = {
        "years": time_diff.days / RATE["TRADING_DAYS_PER_YEAR"],
        "months": time_diff.days / 30.417,
        "weeks": time_diff.days / 7,
        "days": time_diff.days,
        "hours": time_diff.days * 24,
        "minutes": time_diff.total_seconds() / 60,
        "seconds": time_diff.total_seconds()
    }

    if isinstance(tf, str) and tf in TimeFrame.keys():
        return TimeFrame[tf]
    return TimeFrame["years"]


def to_utc(df: DataFrame) -> DataFrame:
    """Either localizes the DataFrame Index to UTC or it applies
    tz_convert to set the Index to UTC.
    """
    if not df.empty:
        try:
            df.index = df.index.tz_localize("UTC")
        except TypeError:
            df.index = df.index.tz_convert("UTC")
    return df


# Aliases
mtd = df_month_to_date
qtd = df_quarter_to_date
ytd = df_year_to_date