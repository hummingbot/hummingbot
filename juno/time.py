import time
from datetime import datetime, timezone

from juno.math import floor_multiple, floor_multiple_offset

SEC_MS = 1000
MIN_MS = 60_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
WEEK_MS = 604_800_000
MONTH_MS = 2_629_746_000
YEAR_MS = 31_556_952_000

MIN_SEC = 60
HOUR_SEC = 3600
DAY_SEC = 86_400
WEEK_SEC = 604_800
MONTH_SEC = 2_629_746
YEAR_SEC = 31_556_952

# 2065-01-24 05:20
MAX_TIME = 3_000_000_000_000

_WEEK_OFFSET_MS = 345_600_000


def now() -> int:
    """Returns current time since EPOCH in milliseconds."""
    return int(round(time.time() * 1000.0))


def format_span(start: int, end: int) -> str:
    return f"{_to_datetime_utc(start)} - " f"{_to_datetime_utc(end)}"


def _to_datetime_utc(ms: int) -> datetime:
    return datetime.utcfromtimestamp(ms / 1000.0).replace(tzinfo=timezone.utc)


def _from_datetime_utc(dt: datetime) -> int:
    assert dt.tzinfo == timezone.utc
    return int(round(dt.timestamp() * 1000.0))


def format_interval(interval: int) -> str:
    result = ""
    remainder = interval
    for letter, factor in _INTERVAL_FACTORS.items():
        quotient, remainder = divmod(remainder, factor)
        if quotient > 0:
            result += f"{quotient}{letter}"
        if remainder == 0:
            break
    return result if result else "0ms"


def format_timestamp(timestamp: int) -> str:
    return _to_datetime_utc(timestamp).isoformat()


def floor_timestamp(timestamp: int, interval: int) -> int:
    if interval < WEEK_MS:
        return floor_multiple(timestamp, interval)
    if interval == WEEK_MS:
        return floor_multiple_offset(timestamp, interval, _WEEK_OFFSET_MS)
    if interval == MONTH_MS:
        dt = _to_datetime_utc(timestamp)
        return _from_datetime_utc(
            dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        )
    raise NotImplementedError()


# Is assumed to be ordered by values descending.
_INTERVAL_FACTORS = {
    "y": YEAR_MS,
    "M": MONTH_MS,
    "w": WEEK_MS,
    "d": DAY_MS,
    "h": HOUR_MS,
    "m": MIN_MS,
    "s": SEC_MS,
    "ms": 1,
}
