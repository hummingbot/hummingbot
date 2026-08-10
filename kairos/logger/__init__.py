import dataclasses
import logging
from decimal import Decimal
from enum import Enum
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING

from .logger import KairosLogger

NETWORK = DEBUG + 6


def log_encoder(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    elif isinstance(obj, Enum):
        return str(obj)
    elif dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)


__all__ = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "NETWORK",
    "KairosLogger",
    "log_encoder"
]
logging.setLoggerClass(KairosLogger)
logging.addLevelName(NETWORK, "NETWORK")
