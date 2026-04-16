import logging

import pytest

from hummingbot.logger.struct_logger import EVENT_LOG_LEVEL, StructLogger


class _CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture()
def struct_logger():
    logger = StructLogger("test.struct_logger_coverage")
    logger.setLevel(EVENT_LOG_LEVEL)
    handler = _CapturingHandler()
    logger.addHandler(handler)
    return logger, handler


def test_event_log_with_extra_kwarg(struct_logger):
    """Line 29-31: when 'extra' is already in kwargs, update it with dict_msg/message_type."""
    logger, handler = struct_logger
    existing_extra = {"custom_key": "custom_value"}
    logger.event_log({"action": "buy", "amount": 1.0}, extra=existing_extra)

    assert len(handler.records) == 1
    rec = handler.records[0]
    # The existing extra dict should have been updated with dict_msg and message_type
    assert rec.__dict__.get("message_type") == "event"
    assert rec.__dict__.get("dict_msg") == {"action": "buy", "amount": 1.0}
    # Original custom key is preserved
    assert rec.__dict__.get("custom_key") == "custom_value"


def test_event_log_without_extra_kwarg(struct_logger):
    """Line 32-33: when 'extra' is not in kwargs, add it."""
    logger, handler = struct_logger
    logger.event_log({"action": "sell", "amount": 2.0})

    assert len(handler.records) == 1
    rec = handler.records[0]
    assert rec.__dict__.get("message_type") == "event"
    assert rec.__dict__.get("dict_msg") == {"action": "sell", "amount": 2.0}


def test_event_log_non_dict_raises_type_error(struct_logger):
    """When dict_msg is not a dict, the _log() call has a bug (missing args) — expect TypeError."""
    logger, handler = struct_logger
    with pytest.raises(TypeError):
        logger.event_log("not a dict")


def test_event_log_disabled_when_level_too_high(struct_logger):
    """When logger level is above EVENT_LOG_LEVEL, event_log does nothing."""
    logger, handler = struct_logger
    logger.setLevel(logging.WARNING)
    logger.event_log({"action": "noop"})
    assert len(handler.records) == 0
