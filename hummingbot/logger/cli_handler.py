#!/usr/bin/env python

from logging import StreamHandler
from typing import Optional


class CLIHandler(StreamHandler):
    def formatException(self, _) -> Optional[str]:
        return None

    def format(self, record) -> str:
        if record.exc_text is not None:
            record.exc_text = None
        retval: str = super().format(record)
        if record.exc_info:
            retval += " (Stack trace dumped to log file)"
        return retval
