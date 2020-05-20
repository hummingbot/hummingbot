import json
import logging

from hummingbot.logger import (
    HummingbotLogger,
    log_encoder,
)

EVENT_LOG_LEVEL = 15
METRICS_LOG_LEVEL = 14
logging.addLevelName(EVENT_LOG_LEVEL, "EVENT_LOG")
logging.addLevelName(METRICS_LOG_LEVEL, "METRIC_LOG")


class StructLogRecord(logging.LogRecord):
    def getMessage(self):
        """
        Return dict msg if present
        """
        if "dict_msg" in self.__dict__ and isinstance(self.__dict__["dict_msg"], dict):
            return json.dumps(self.__dict__["dict_msg"], default=log_encoder)
        else:
            return super().getMessage()


class StructLogger(HummingbotLogger):
    def event_log(self, dict_msg, *args, **kwargs):
        if self.isEnabledFor(EVENT_LOG_LEVEL):
            if not isinstance(dict_msg, dict):
                self._log(logging.ERROR, "event_log message must be of type dict.", extra={"do_not_send": True})
                return
            extra = {
                "dict_msg": dict_msg,
                "message_type": "event"
            }
            if "extra" in kwargs:
                kwargs["extra"].update(extra)
            else:
                kwargs["extra"] = extra

            self._log(EVENT_LOG_LEVEL, "", args, **kwargs)
