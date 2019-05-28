import asyncio
import logging
from hummingbot.logger.struct_logger import StructLogger
from collections import defaultdict
from typing import Optional
REPORT_EVENT_QUEUE = asyncio.Queue()


class ReportAggregator:
    ra_logger: Optional[StructLogger] = None

    @classmethod
    def logger(cls) -> StructLogger:
        if cls.ra_logger is None:
            cls.ra_logger = logging.getLogger(__name__)
        return cls.ra_logger

    def __init__(self, hummingbot_app: "HummingbotApplication",
                 report_aggregation_interval: float = 60.0,
                 log_report_interval: float = 60.0):

        self.log_report_interval: float = log_report_interval
        self.report_aggregation_interval: float = report_aggregation_interval
        self.stats: dict = defaultdict(list)
        self.hummingbot_app: "HummingbotApplication" = hummingbot_app
        self.get_open_order_stats_task: Optional[asyncio.Task] = None
        self.get_event_task: Optional[asyncio.Task] = None
        self.log_report_task: Optional[asyncio.Task] = None

    def receive_event(self, event):

        event_name = event["event_name"]
        if event_name == "OrderFilledEvent":
            self.stats[f"order_filled_quote_volume.{event['event_source']}."
                       f"{str(event['trade_type']).replace('.', '-')}."
                       f"{str(event['order_type']).replace('.', '-')}.{event['symbol']}"].append(
                (event["ts"], event["price"] * event["amount"])
            )

    async def log_report(self):
        while True:
            try:
                # Handle clock is None error when the bot stops and restarts
                if self.hummingbot_app.clock is not None:
                    for metric_name, value_list in self.stats.items():
                        if not value_list:
                            continue
                        namespaces = metric_name.split(".")

                        if namespaces[0] == "open_order_quote_volume_sum":
                            avg_volume = float(sum([value[1] for value in value_list]) / len(value_list))
                            self.logger().metric_log({
                                "metric": "hummingbot_client.open_order_quote_volume_sum",
                                "type": "gauge",
                                "points": [[self.hummingbot_app.clock.current_timestamp, avg_volume]],
                                "tags": [f"symbol:{namespaces[2]}",
                                         f"market:{namespaces[1]}"]
                            })
                            self.stats[metric_name] = []
                        if namespaces[0] == "order_filled_quote_volume":
                            sum_volume = float(sum([value[1] for value in value_list]))
                            self.logger().metric_log({
                                "metric": "hummingbot_client.order_filled_quote_volume",
                                "type": "gauge",
                                "points": [[self.hummingbot_app.clock.current_timestamp, sum_volume]],
                                "tags": [f"symbol:{namespaces[4]}",
                                         f"market:{namespaces[1]}",
                                         f"order_side:{namespaces[2]}",
                                         f"order_type:{namespaces[3]}"]

                            })
                            self.stats[metric_name] = []
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Error getting logging report.", exc_info=True, extra={"do_not_send": True})

            await asyncio.sleep(self.log_report_interval)

    async def get_open_order_stats(self):
        while True:
            try:
                if not (self.hummingbot_app.strategy and hasattr(self.hummingbot_app.strategy, "active_maker_orders")):
                    await asyncio.sleep(5.0)
                    continue

                _open_orders = defaultdict(list)

                for maker_market, order in self.hummingbot_app.strategy.active_maker_orders:
                    key = f"{maker_market.__class__.__name__}.{order.symbol}"
                    _open_orders[key].append(order.price * order.quantity)
                for market_name, quote_volumes in _open_orders.items():
                    metric_name = f"open_order_quote_volume_sum.{market_name}"
                    metric_value = (self.hummingbot_app.clock.current_timestamp, sum(quote_volumes))
                    self.stats[metric_name].append(metric_value)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Error getting open orders.", exc_info=True, extra={"do_not_send": True})

            await asyncio.sleep(self.report_aggregation_interval)

    async def get_event(self):
        while True:
            try:
                event = await REPORT_EVENT_QUEUE.get()
                self.receive_event(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Error processing events. {event}", exc_info=True, extra={"do_not_send": True})

    def start(self):
        self.stop()
        self.get_open_order_stats_task = asyncio.ensure_future(self.get_open_order_stats())
        self.get_event_task = asyncio.ensure_future(self.get_event())
        self.log_report_task = asyncio.ensure_future(self.log_report())

    def stop(self):
        if self.log_report_task:
            self.log_report_task.cancel()
        if self.get_open_order_stats_task:
            self.get_open_order_stats_task.cancel()
        if self.get_event_task:
            self.get_event_task.cancel()
