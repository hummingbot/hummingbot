#!/usr/bin/env python

from logging import StreamHandler
from typing import Optional


class CLIHandler(StreamHandler):
    def formatException(self, _) -> Optional[str]:
        return None

    def format(self, record) -> str:
        exc_info = record.exc_info
        if record.exc_info is not None:
            record.exc_info = None
        retval: str = super().format(record)
        if exc_info:
            retval += " (See log file for stack trace dump)"
        record.exc_info = exc_info
        return retval
