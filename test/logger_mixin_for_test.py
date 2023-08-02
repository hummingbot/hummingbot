import asyncio
import logging
from logging import Handler, LogRecord
from types import UnionType
from typing import Callable, List, Protocol

from async_timeout import timeout

from hummingbot.logger import HummingbotLogger


class LogLevel:
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


_IntOrStr: UnionType = int | str


class LoggerMixinProtocol(Protocol):
    level: _IntOrStr
    log_records: List[LogRecord]


class _LoggerProtocol(LoggerMixinProtocol, Protocol):
    def setLevel(self, level: _IntOrStr):
        ...

    def addHandler(self, handler: Handler):
        ...


class LoggerMixinForTest(LoggerMixinProtocol):
    """
    Test logger mixin class that can be used to capture log records during testing.

    This mixin provides methods to handle log records and check if specific messages at certain levels are logged.

    Example usage:
    ```python
    class MyTestCase(unittest.TestCase, LoggerMixinForTest):
        def test_something(self):
            self.logger.info("Testing...")
            self.assertTrue(self.is_logged("Testing...", logging.INFO))
    ```

    Attributes:
    - `level`: The default log level for the logger.
    """
    level: _IntOrStr = LogLevel.NOTSET

    def _initialize(self: _LoggerProtocol):
        """
        Initialize the test logger mixin by setting the default log level and initializing the log records list.
        """
        self.level: _IntOrStr = 1
        self.log_records: List[LogRecord] = []

    @staticmethod
    def _to_loglevel(log_level: _IntOrStr) -> str:
        """
        Convert a log level to a string.
        :params int | str log_level: The log level to convert.
        """
        if isinstance(log_level, int):
            log_level = logging.getLevelName(log_level)
        return log_level

    def set_loggers(self, loggers: List[HummingbotLogger] | HummingbotLogger):
        """
        Set up the test logger mixin by adding the test logger to the provided loggers list.
        :params List[HummingbotLogger] | HummingbotLogger loggers: The loggers to add to the LoggerMixinForTest.
        """
        # __init__() may not be called if the class is used as a mixin
        if not hasattr(self, "log_records"):
            self._initialize()

        if isinstance(loggers, HummingbotLogger):
            loggers = [loggers]

        for logger in loggers:
            if logger is not None:
                logger.setLevel(self.level)
                logger.addHandler(self)

    def handle(self, record: LogRecord):
        """
        Handle a log record by appending it to the log records list.
        :params LogRecord record: The log record to handle.
        """
        self.log_records.append(record)

    def is_logged(self, log_level: _IntOrStr, message: str) -> bool:
        """
        Check if a certain message has been logged at a certain level.
        :params int | str log_level: The log level to check.
        :params str message: The message to check.
        """
        log_level = self._to_loglevel(log_level)
        return any(
            record.getMessage() == message and record.levelname == log_level
            for record in self.log_records
        )

    def is_partially_logged(self, log_level: _IntOrStr, message: str) -> bool:
        """
        Check if a certain message has been 'partially' logged at a certain level.
        This is useful for checking if a message has been logged with a dynamic value.
        :params int | str log_level: The log level to check.
        :params str message: The message to check.
        """
        log_level = self._to_loglevel(log_level)
        return any(
            message in record.getMessage() and record.levelname == log_level
            for record in self.log_records
        )

    async def wait_for_logged(self,
                              log_level: _IntOrStr,
                              message: str,
                              partial: bool = False,
                              wait_s: float = 3) -> None:
        """
        Wait for a certain message to be logged at a certain level.
        :params int | str log_level: The log level to check.
        :params str message: The message to check.
        :params bool partial: Whether to check if the message is partially logged.
        :params float wait_s: The number of seconds to wait before timing out.
                """
        log_level = self._to_loglevel(log_level)
        log_method: Callable[[str | int, str], bool] = self.is_partially_logged if partial else self.is_logged
        try:
            async with timeout(wait_s):
                while not log_method(log_level, message):
                    await asyncio.sleep(0.1)
        except asyncio.TimeoutError as e:
            # Used within a class derived from unittest.TestCase
            if callable(getattr(self, "fail", None)):
                getattr(self, "fail")(f"Message: {message} was not logged.\n"
                                      f"Received Logs: {[record.getMessage() for record in self.log_records]}")
            else:
                print(f"Message: {message} was not logged.")
                print(f"Received Logs: {[record.getMessage() for record in self.log_records]}")
                raise e
