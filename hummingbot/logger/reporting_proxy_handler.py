#!/usr/bin/env python

import io
from os.path import (
    realpath,
    join
)
import json
import logging
import traceback
from typing import Optional

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.logger import (
    HummingbotLogger,
    log_encoder
)
from hummingbot.logger.log_server_client import LogServerClient


VERSIONFILE = realpath(join(__file__, "../../VERSION"))
CLIENT_VERSION = open(VERSIONFILE, "rt").read()


class ReportingProxyHandler(logging.Handler):
    _rrh_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._rrh_logger is None:
            cls._rrh_logger = logging.getLogger(__name__)
        return cls._rrh_logger

    def __init__(self,
                 level=logging.ERROR,
                 proxy_url="https://127.0.0.1:9000",
                 capacity=1):
        super().__init__()
        self.setLevel(level)
        self._log_queue: list = []
        self.capacity: int = capacity
        self.proxy_url: str = proxy_url
        self.log_server_client: LogServerClient = LogServerClient.get_instance()

    @property
    def client_id(self):
        return global_config_map["client_id"].value or ""

    def emit(self, record):
        if record.__dict__.get("do_not_send", False):
            return
        if not self.log_server_client.started:
            self.log_server_client.start()
        log_type = record.__dict__.get("message_type", "log")
        if not log_type == "event":
            self.process_log(record)
        self.flush()

    def formatException(self, ei):
        """
        Format and return the specified exception information as a string.

        This default implementation just uses
        traceback.print_exception()
        """
        sio = io.StringIO()
        tb = ei[2]
        # See issues #9427, #1553375 in python logging. Commented out for now.
        # if getattr(self, 'fullstack', False):
        #     traceback.print_stack(tb.tb_frame.f_back, file=sio)
        traceback.print_exception(ei[0], ei[1], tb, None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1:] == "\n":
            s = s[:-1]
        return s

    def process_log(self, log):
        message = {
            "name": log.name,
            "funcName": log.funcName,
            "msg": log.getMessage(),
            "created": log.created,
            "level": log.levelname
        }
        if log.exc_info:
            message["exc_info"] = self.formatException(log.exc_info)
            message["exception_type"] = str(log.exc_info[0])
            message["exception_msg"] = str(log.exc_info[1])
        self._log_queue.append(message)

    def send_logs(self, logs):
        request_obj = {
            "url": f"{self.proxy_url}/logs",
            "method": "POST",
            "request_obj": {
                "headers": {
                    'Content-Type': "application/json"
                },
                "data": json.dumps(logs, default=log_encoder),
                "params": {"ddtags": f"client_id:{self.client_id},"
                                     f"client_version:{CLIENT_VERSION},"
                                     f"type:log",
                           "ddsource": "hummingbot-client"}
            }
        }
        self.log_server_client.request(request_obj)

    def flush(self, send_all=False):
        self.acquire()
        min_send_capacity = self.capacity
        if send_all:
            min_send_capacity = 0
        try:
            if global_config_map["send_error_logs"].value:
                if len(self._log_queue) > min_send_capacity:
                    self.send_logs(self._log_queue)
                    self._log_queue = []
        except Exception:
            self.logger().error(f"Error sending logs.", exc_info=True, extra={"do_not_send": True})
        finally:
            self.release()

    def close(self):
        try:
            self.flush(send_all=True)
            self.log_server_client.stop()
        finally:
            logging.Handler.close(self)
