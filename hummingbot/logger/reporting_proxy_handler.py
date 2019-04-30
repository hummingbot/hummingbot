from typing import Optional
import logging
import json
from hummingbot.cli.config.global_config_map import global_config_map
from wings.logger.struct_logger import log_encoder
from hummingbot.logger.log_server_client import LogServerClient
from hummingbot.logger.report_aggregator import REPORT_EVENT_QUEUE


class ReportingProxyHandler(logging.Handler):
    rrh_logger: Optional[logging.Logger] = None
    @classmethod
    def logger(cls) -> logging.Logger:
        if cls.rrh_logger is None:
            cls.rrh_logger = logging.getLogger(__name__)
        return cls.rrh_logger

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

    def process_log(self, log):
        message = {
            "name": log.name,
            "funcName": log.funcName,
            "msg": log.getMessage(),
            "created": log.created,
            "level": log.levelname,
        }
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
                "params": {"ddtags": f"client_id:{self.client_id},type:log",
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
                "params": {"ddtags": f"client_id:{self.client_id},type:event",
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
