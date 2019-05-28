import logging
from logging import (
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL
)


from .logger import HummingbotLogger

NETWORK = DEBUG + 6

__all__ = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "NETWORK",
    "HummingbotLogger"
]
logging.setLoggerClass(HummingbotLogger)
logging.addLevelName(NETWORK, "NETWORK")
