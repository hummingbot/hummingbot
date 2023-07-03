import asyncio
import logging
from logging import Handler, LogRecord
from typing import Callable, List, Protocol, Union

from async_timeout import timeout

from hummingbot.logger.logger import HummingbotLogger


class LogLevel:
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class TestLoggerMixinProtocol(Protocol):
    level: Union[int, str]
    log_records: List[LogRecord]


class _LoggerProtocol(TestLoggerMixinProtocol, Protocol):
    def setLevel(self, level: Union[str, LogLevel]):
        ...

    def addHandler(self, handler: Handler):
        ...


class TestLoggerMixin(Handler):
    """
    Test logger mixin class that can be used to capture log records during testing.

    This mixin provides methods to handle log records and check if specific messages at certain levels are logged.

    Example usage:
    ```python
    class MyTestCase(unittest.TestCase, TestLoggerMixin):
        def test_something(self):
            self.logger.info("Testing...")
            self.assertTrue(self.is_logged("Testing...", logging.INFO))
    ```

    Attributes:
    - `level`: The default log level for the logger.
    """
    level: Union[int, str] = LogLevel.NOTSET

    def _initialize(self: _LoggerProtocol):
        self.log_records: List[LogRecord] = []

    @staticmethod
    def _to_loglevel(log_level: Union[str, int]) -> str:
        if isinstance(log_level, int):
            log_level = logging.getLevelName(log_level)
        return log_level

    def set_loggers(self, loggers: List[HummingbotLogger]):
        """
        Set up the test logger mixin by adding the test logger to the provided loggers list.
        """
        # __init__() may not be called if the class is used as a mixin
        # We forcefully create or initialize the log_records attribute here
        self._initialize()
        for logger in loggers:
            if logger is not None:
                logger.setLevel(1)
                logger.addHandler(self)

    def handle(self, record: LogRecord):
        """
        Handle a log record by appending it to the log records list.
        """
        self.log_records.append(record)

    def is_logged(self, log_level: Union[str, int], message: str):
        """
        Check if a certain message has been logged at a certain level.
        """
        log_level = self._to_loglevel(log_level)
        return any([record.getMessage() == message and record.levelname == log_level for record in self.log_records])

    def is_partially_logged(self, log_level: Union[str, int], message: str):
        """
        Check if a part of a certain message has been logged at a certain level.
        """
        log_level = self._to_loglevel(log_level)
        return any([message in record.getMessage() and record.levelname == log_level for record in self.log_records])

    async def wait_for_logged(self,
                              log_level: str,
                              message: str,
                              partial: bool = False,
                              wait_s: float = 3) -> None:
        """
        Wait for a certain message to be logged at a certain level.
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
