import unittest
from logging import LogRecord
from test.logger_mxin import LogLevel, TestLoggerMixin


class TestTestLoggerMixin(unittest.TestCase):
    def setUp(self):
        self.logger = TestLoggerMixin()

    def test_handle(self):
        record = LogRecord(name="test", level=LogLevel.INFO, pathname="", lineno=0, msg="test message", args=None,
                           exc_info=None)
        self.logger.handle(record)
        self.assertEqual(len(self.logger.log_records), 1)
        self.assertEqual(self.logger.log_records[0].getMessage(), "test message")

    def test_is_logged(self):
        record = LogRecord(name="test", level=LogLevel.INFO, pathname="", lineno=0, msg="test message", args=None,
                           exc_info=None)
        self.logger.handle(record)
        self.assertTrue(self.logger.is_logged("test message", LogLevel.INFO))
        self.assertFalse(self.logger.is_logged("test message", LogLevel.ERROR))
        self.assertFalse(self.logger.is_logged("other message", LogLevel.INFO))

    def test_is_partially_logged(self):
        record = LogRecord(name="test", level=LogLevel.INFO, pathname="", lineno=0, msg="test message", args=None,
                           exc_info=None)
        self.logger.handle(record)
        self.assertTrue(self.logger.is_partially_logged("test", LogLevel.INFO))
        self.assertFalse(self.logger.is_partially_logged("test", LogLevel.ERROR))
        self.assertFalse(self.logger.is_partially_logged("other", LogLevel.INFO))


if __name__ == "__main__":
    unittest.main()
