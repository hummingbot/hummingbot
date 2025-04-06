import logging
from typing import Optional
import dataclasses
from hummingbot.core.event.event_listener cimport EventListener

er_logger = None

cdef class EventReporter(EventListener):
    """
    Event listener that log events to logger
    """
    def __init__(self, event_source: Optional[str] = None):
        super().__init__()
        self.event_source = event_source

    @classmethod
    def logger(cls):
        global er_logger
        if er_logger is None:
            er_logger = logging.getLogger(__name__)
        return er_logger

    cdef c_call(self, object event_object):
        try:
            if dataclasses.is_dataclass(event_object):
                event_dict = dataclasses.asdict(event_object)
            else:
                event_dict = event_object._asdict()

            event_dict.update({"event_name": event_object.__class__.__name__,
                               "event_source": self.event_source})
            self.logger().event_log(event_dict)
        except Exception:
            self.logger().error("Error logging events.", exc_info=True)
