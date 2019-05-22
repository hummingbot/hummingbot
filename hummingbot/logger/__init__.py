import logging
from logging import (
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL
)


from .logger import HummingbotLogger

NETWORK_ERROR = DEBUG + 5

__all__ = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "NETWORK_ERROR",
    "HummingbotLogger"
]
logging.setLoggerClass(HummingbotLogger)
