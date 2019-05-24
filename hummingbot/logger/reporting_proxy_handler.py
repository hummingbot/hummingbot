import io
import traceback
from typing import Optional
import logging
import json
from hummingbot.cli.config.global_config_map import global_config_map
from wings.logger.struct_logger import log_encoder
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.log_server_client import LogServerClient
from hummingbot.logger.report_aggregator import REPORT_EVENT_QUEUE


VERSIONFILE="hummingbot/VERSION"
CLIENT_VERSION = open(VERSIONFILE, "rt").read()


class ReportingProxyHandler(logging.Handler):
    _rrh_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._rrh_logger is None:
            cls._rrh_logger = logging.getLogger(__name__)
        return cls._rrh_logger

    def __init__(self,
                 level=logging.INFO,
                 proxy_url="https://127.0.0.1:9000",
                 capacity=1):
        super().__init__()
        self.setLevel(level)
        self._log_queue: list = []
        self._event_queue: list = []
        self._metrics_queue: list = []
        self.capacity: int = capacity
        self.proxy_url: str = proxy_url
        self.log_server_client: LogServerClient = LogServerClient.get_instance()
        self.log_server_client.start()

    @property
    def client_id(self):
        return global_config_map["client_id"].value

    def emit(self, record):
        if record.__dict__.get("do_not_send", False):
            return
        log_type = record.__dict__.get("message_type", "log")
        if log_type == "event":
            self.process_event_log(record)
        elif log_type == "metric":
            self.process_metric_log(record)
        else:
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
        #if getattr(self, 'fullstack', False):
        #    traceback.print_stack(tb.tb_frame.f_back, file=sio)
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

    def process_event_log(self, log):
        event_dict = log.__dict__.get("dict_msg", {})
        if "timestamp" in event_dict:
            event_dict["ts"] = event_dict["timestamp"]
            del event_dict["timestamp"]

        if event_dict:
            REPORT_EVENT_QUEUE.put_nowait(event_dict)
            self._event_queue.append(event_dict)

    def process_metric_log(self, log):
        metric_dict = log.__dict__.get("dict_msg", {})
        if metric_dict:
            metric_dict["tags"] = metric_dict.get("tags", []) + \
                                  [f"client_id:{self.client_id}", "source:hummingbot-client"]

            self._metrics_queue.append(metric_dict)

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

    def send_event_logs(self, logs):
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
                                     f"type:event",
                           "ddsource": "hummingbot-client"}
            }
        }
        self.log_server_client.request(request_obj)

    def send_metric_logs(self, logs):
        request_obj = {
            "url": f"{self.proxy_url}/metrics",
            "method": "POST",
            "request_obj": {
                "headers": {
                    'Content-Type': "application/json"
                },
                "data": json.dumps(
                    {"series": logs},
                    default=log_encoder
                )
            }
        }
        self.log_server_client.request(request_obj)

    def flush(self, send_all=False):
        self.acquire()
        min_send_capacity = self.capacity
        if send_all:
            min_send_capacity = 0
        try:
            if len(self._log_queue) > min_send_capacity:
                self.send_logs(self._log_queue)
                self._log_queue = []
            if len(self._event_queue) > min_send_capacity:
                self.send_event_logs(self._event_queue)
                self._event_queue = []
            if len(self._metrics_queue) > min_send_capacity:
                self.send_metric_logs(self._metrics_queue)
                self._metrics_queue = []

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
