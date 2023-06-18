import unittest
from logging import Logger, LogRecord
from test.logger_mxin import LogLevel, TestLoggerMixin

from hummingbot.logger import HummingbotLogger


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

    def test_set_loggers_single_logger(self):
        logger = HummingbotLogger("TestLogger")
        logger.level = LogLevel.INFO
        self.assertNotEqual(logger.level, self.logger.level)
        self.assertEqual(0, len(logger.handlers))

        self.logger.set_loggers([logger])
        self.assertEqual(logger.level, self.logger.level)
        self.assertEqual(1, len(logger.handlers))
        self.assertEqual(self.logger, logger.handlers[0])

    def test_set_loggers_multiple_logger(self):
        loggers = []
        for i in range(5):
            logger = HummingbotLogger(f"TestLogger{i}")
            logger.level = LogLevel.INFO
            loggers.append(logger)
            self.assertNotEqual(logger.level, self.logger.level)
            self.assertEqual(0, len(logger.handlers))

        self.logger.set_loggers(loggers)

        for logger in loggers:
            self.assertEqual(logger.level, self.logger.level)
            self.assertEqual(1, len(logger.handlers))
            self.assertEqual(self.logger, logger.handlers[0])

    def test_set_loggers_other_logger(self):
        logger = Logger("TestLogger")
        logger.level = LogLevel.INFO
        self.assertNotEqual(logger.level, self.logger.level)
        self.assertEqual(0, len(logger.handlers))

        self.logger.set_loggers([logger])
        self.assertEqual(logger.level, self.logger.level)
        self.assertEqual(1, len(logger.handlers))
        self.assertEqual(self.logger, logger.handlers[0])

    def test_set_loggers_some_none(self):
        loggers = [HummingbotLogger("Test"), None]
        self.logger.set_loggers(loggers)


if __name__ == "__main__":
    unittest.main()
