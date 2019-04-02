#!/usr/bin/env python

import logging
from concurrent.futures import ThreadPoolExecutor

__all__ = ["root_path", "get_executor"]

from .logger.struct_logger import (
    StructLogRecord,
    StructLogger
)
# Do not raise exceptions during log handling
logging.setLogRecordFactory(StructLogRecord)
logging.setLoggerClass(StructLogger)

_shared_executor = None


def root_path() -> str:
    from os.path import realpath, join
    return realpath(join(__file__, "../../"))


def get_executor() -> ThreadPoolExecutor:
    global _shared_executor
    if _shared_executor is None:
        _shared_executor = ThreadPoolExecutor()
    return _shared_executor
