import logging

from hummingbot.logger.cli_handler import CLIHandler


def test_format_with_exc_info_set():
    """Line 15: format() when record.exc_info is not None — clears it temporarily."""
    handler = CLIHandler()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="something went wrong",
        args=(),
        exc_info=(ValueError, ValueError("boom"), None),
    )
    result = handler.format(record)
    assert isinstance(result, str)
    assert "something went wrong" in result
    assert "(See log file for stack trace dump)" in result
    # exc_info must be restored after format()
    assert record.exc_info is not None


def test_format_without_exc_info():
    """format() when record.exc_info is None — no stack trace note appended."""
    handler = CLIHandler()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="all good",
        args=(),
        exc_info=None,
    )
    result = handler.format(record)
    assert isinstance(result, str)
    assert "all good" in result
    assert "(See log file for stack trace dump)" not in result


def test_format_exception_returns_none():
    """formatException always returns None (suppresses stack trace in stream)."""
    handler = CLIHandler()
    assert handler.formatException(None) is None
    assert handler.formatException(("type", "value", "tb")) is None
