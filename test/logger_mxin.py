from logging import LogRecord
from typing import List


class LogLevel:
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class TestLoggerMixin:
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
    level = LogLevel.NOTSET

    def __init__(self, *args, **kwargs):
        if super().__class__ is not object:
            super().__init__(*args, **kwargs)
        self.log_records: List[LogRecord] = []

    def handle(self, record):
        """
        Handle a log record by appending it to the log records list.
        """
        self.log_records.append(record)

    def is_logged(self, msg, level):
        """
        Check if a certain message has been logged at a certain level.
        """
        return any([record.getMessage() == msg and record.levelno == level for record in self.log_records])

    def is_partially_logged(self, msg, level):
        """
        Check if a part of a certain message has been logged at a certain level.
        """
        return any([msg in record.getMessage() and record.levelno == level for record in self.log_records])
