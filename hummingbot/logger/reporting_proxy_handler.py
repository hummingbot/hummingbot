#!/usr/bin/env python

import io
from os.path import (
    realpath,
    join
)
import json
import logging
import traceback
from typing import Optional, List, Dict, Tuple, Any, Union
import threading
import asyncio

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.logger import (
    HummingbotLogger,
    log_encoder
)
from hummingbot.logger.log_server_client import LogServerClient
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import OrderFilledEvent, MarketEvent, BuyOrderCreatedEvent, SellOrderCreatedEvent
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future


VERSIONFILE = realpath(join(__file__, "../../VERSION"))
CLIENT_VERSION = open(VERSIONFILE, "rt").read()


class ReportingProxyHandler(logging.Handler):
    _rrh_logger: Optional[HummingbotLogger] = None
    _shared_instance: "ReportingProxyHandler" = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._rrh_logger is None:
            cls._rrh_logger = logging.getLogger(__name__)
        return cls._rrh_logger

    @classmethod
    def get_instance(cls, level=logging.ERROR,
                     proxy_url="http://127.0.0.1:9000",
                     capacity=1) -> "ReportingProxyHandler":
        if cls._shared_instance is None:
            cls._shared_instance = ReportingProxyHandler(level, proxy_url, capacity)
        return cls._shared_instance

    def __init__(self,
                 level=logging.ERROR,
                 proxy_url="http://127.0.0.1:9000",
                 capacity=1):
        super().__init__()
        self.setLevel(level)
        self._log_queue: list = []
        self._event_queue: list = []
        self._capacity: int = capacity
        self._proxy_url: str = proxy_url
        self._log_server_client: Optional[LogServerClient] = None
        self._order_filled_events: Dict[str, List[OrderFilledEvent]] = {}
        self._order_created_events: Dict[str, List[Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]]] = {}
        self._fill_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_fill_order)
        self._create_order_forwarder: SourceInfoEventForwarder = SourceInfoEventForwarder(self._did_create_order)
        self._send_aggregated_metrics_loop_task = None
        self._markets: List[ConnectorBase] = []
        self._event_pairs: List[Tuple[MarketEvent, SourceInfoEventForwarder]] = [
            (MarketEvent.BuyOrderCreated, self._create_order_forwarder),
            (MarketEvent.SellOrderCreated, self._create_order_forwarder),
            (MarketEvent.OrderFilled, self._fill_order_forwarder),
        ]

    @property
    def log_server_client(self):
        if not self._log_server_client:
            self._log_server_client = LogServerClient.get_instance(log_server_url=self._proxy_url)
        return self._log_server_client

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
        else:
            self.process_event(record)
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

        if not message.get("msg"):
            return
        self._log_queue.append(message)

    def process_event(self, log):
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

        if not message.get("msg"):
            return
        self._event_queue.append(message)

    def send_logs(self, logs):
        request_obj = {
            "url": f"{self._proxy_url}/logs",
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

    def send_events(self, logs):
        request_obj = {
            "url": f"{self._proxy_url}/order-event",
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

    def send_metric(self, metric_name: str, exchange: str, market: str, value: Any):
        request_obj = {
            "url": f"{self._proxy_url}/{metric_name}",
            "method": "POST",
            "request_obj": {
                "headers": {
                    'Content-Type': "application/json"
                },
                "data": json.dumps({"client_id": self.client_id, "exchange": exchange, "market": market,
                                    f"{metric_name}": str(value)})
            }
        }
        self.log_server_client.request(request_obj)

    def flush(self, send_all=False):
        self.acquire()
        min_send_capacity = self._capacity
        if send_all:
            min_send_capacity = 0
        try:
            if global_config_map["send_error_logs"].value:
                if len(self._log_queue) > 0 and len(self._log_queue) >= min_send_capacity:
                    self.send_logs(self._log_queue)
                    self._log_queue = []
            if len(self._event_queue) > 0 and len(self._event_queue) >= min_send_capacity:
                self.send_events(self._event_queue)
                self._event_queue = []
        except Exception:
            self.logger().error("Error sending logs.", exc_info=True, extra={"do_not_send": True})
        finally:
            self.release()

    def close(self):
        try:
            self.flush(send_all=True)
            self.log_server_client.stop()
            if self._send_aggregated_metrics_loop_task is not None:
                self._send_aggregated_metrics_loop_task.cancel()
                self._send_aggregated_metrics_loop_task = None
        finally:
            logging.Handler.close(self)

    def set_markets(self, markets: List[ConnectorBase], heartbeat_interval_min: float):
        self._markets = markets
        for market in self._markets:
            for event_pair in self._event_pairs:
                market.add_listener(event_pair[0], event_pair[1])
        if self._send_aggregated_metrics_loop_task is None:
            self._send_aggregated_metrics_loop_task = safe_ensure_future(
                self.send_aggregated_metrics_loop(heartbeat_interval_min))

    async def send_aggregated_metrics_loop(self, heartbeat_interval_min: float):
        while True:
            try:
                for connector_name, filled_events in self._order_filled_events.copy().items():
                    pairs = set(e.trading_pair for e in filled_events)
                    for pair in pairs:
                        filled_trades = [e for e in filled_events if e.trading_pair == pair]
                        traded_volume = sum(e.price * e.amount for e in filled_trades)
                        self.send_metric("filled_quote_volume", connector_name, pair, traded_volume)
                        self.send_metric("trade_count", connector_name, pair, len(filled_trades))
                self._order_filled_events.clear()

                for connector_name, created_events in self._order_created_events.copy().items():
                    pairs = set(e.trading_pair for e in created_events)
                    for pair in pairs:
                        created_orders = [e for e in created_events if e.trading_pair == pair]
                        self.send_metric("order_count", connector_name, pair, len(created_orders))
                self._order_created_events.clear()

                await asyncio.sleep(60 * heartbeat_interval_min)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while sending aggregated metrics.", exc_info=True)
                return

    def _did_fill_order(self,
                        event_tag: int,
                        market: ConnectorBase,
                        evt: OrderFilledEvent):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_fill_order, event_tag, market, evt)
            return
        if market.name not in self._order_filled_events:
            self._order_filled_events[market.name] = []
        self._order_filled_events[market.name].append(evt)

    def _did_create_order(self,
                          event_tag: int,
                          market: ConnectorBase,
                          evt: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if threading.current_thread() != threading.main_thread():
            self._ev_loop.call_soon_threadsafe(self._did_create_order, event_tag, market, evt)
            return
        if market.name not in self._order_created_events:
            self._order_created_events[market.name] = []
        self._order_created_events[market.name].append(evt)
