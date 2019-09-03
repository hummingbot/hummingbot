#!/usr/bin/env python

from typing import (
    NamedTuple,
    Tuple,
    Optional
)


class ApplicationWarning(NamedTuple):
    timestamp: float
    logger_name: str
    caller_info: Tuple[str, int, str, Optional[str]]
    warning_msg: str
