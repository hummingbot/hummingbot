import logging
from logging import Handler, LogRecord
from typing import List, Protocol, Union

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

    def set_loggers(self, loggers: List[HummingbotLogger]):
        """
        Set up the test logger mixin by adding the test logger to the provided loggers list.
        """
        # __init__() may not be called if the class is used as a mixin
        # We forcefully create or initialize the log_records attribute here
        self._initialize()
        for logger in loggers:
            if logger is not None:
                logger.setLevel(self.level)
                logger.addHandler(self)

    def handle(self, record: LogRecord):
        """
        Handle a log record by appending it to the log records list.
        """
        self.log_records.append(record)

    def is_logged(self, level: Union[str, int], msg: str):
        """
        Check if a certain message has been logged at a certain level.
        """
        if isinstance(level, int):
            level = logging.getLevelName(level)

        return any([record.getMessage() == msg and record.levelname == level for record in self.log_records])

    def is_partially_logged(self, level: Union[str, LogLevel], msg: str):
        """
        Check if a part of a certain message has been logged at a certain level.
        """
        if isinstance(level, int):
            level = logging.getLevelName(level)

        return any([msg in record.getMessage() and record.levelname == level for record in self.log_records])
