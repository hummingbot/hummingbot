import asyncio
import copy
import logging

from hummingbot.logger import REPORT_EVENT_QUEUE
from hummingbot.logger.struct_logger import StructLogger
from collections import defaultdict
from typing import Optional
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.bittrex.bittrex_market import BittrexMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.ddex.ddex_market import DDEXMarket
from hummingbot.market.huobi.huobi_market import HuobiMarket
from hummingbot.market.idex.idex_market import IDEXMarket
from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket

MARKETS = {
    "ddex": DDEXMarket,
    "coinbase_pro": CoinbaseProMarket,
    "binance": BinanceMarket,
    "bamboo_relay": BambooRelayMarket,
    "radar_relay": RadarRelayMarket,
    "idex": IDEXMarket,
    "huobi": HuobiMarket,
    "bittrex": BittrexMarket
}


class ReportAggregator:
    ra_logger: Optional[StructLogger] = None

    @classmethod
    def logger(cls) -> StructLogger:
        if cls.ra_logger is None:
            cls.ra_logger = logging.getLogger(__name__)
        return cls.ra_logger

    def __init__(self, hummingbot_app: "HummingbotApplication",  # noqa: F821
                 report_aggregation_interval: float = 60.0,
                 log_report_interval: float = 60.0):

        self.log_report_interval: float = log_report_interval
        self.report_aggregation_interval: float = report_aggregation_interval
        self.stats: dict = defaultdict(list)
        self.hummingbot_app: "HummingbotApplication" = hummingbot_app  # noqa: F821
        self.get_open_order_stats_task: Optional[asyncio.Task] = None
        self.get_event_task: Optional[asyncio.Task] = None
        self.log_report_task: Optional[asyncio.Task] = None
        self.exchange_converter: ExchangeRateConversion = ExchangeRateConversion().get_instance()

    def receive_event(self, event):
        event_name = event["event_name"]
        if event_name == "OrderFilledEvent":
            self.stats[f"order_filled_quote_volume.{event['event_source']}.{event['symbol']}."
                       f"{str(event['trade_type']).replace('.', '-')}."
                       f"{str(event['order_type']).replace('.', '-')}"].append(
                (event["ts"], event["price"] * event["amount"])
            )

    async def log_report(self):
        while True:
            try:
                # Handle clock is None error when the bot stops and restarts
                if self.hummingbot_app.clock is not None:
                    stats = copy.deepcopy(self.stats)
                    self.stats = defaultdict(list)
                    for metric_name, value_list in stats.items():
                        if not value_list:
                            continue
                        namespaces = metric_name.split(".")
                        market_name = namespaces[1]
                        trading_pair = namespaces[2]
                        quote_token = MARKETS[market_name].split_symbol(trading_pair)[1].upper()
                        if namespaces[0] == "open_order_quote_volume_sum":
                            avg_volume = float(sum([value[1] for value in value_list]) / len(value_list))
                            usd_avg_volume = self.exchange_converter.exchange_rate.get(quote_token, 1) * avg_volume
                            metric_attributes = {
                                "type": "gauge",
                                "tags": [f"symbol:{trading_pair}",
                                         f"market:{market_name}"]
                            }
                            open_order_quote_volume_sum_metrics = {
                                "metric": "hummingbot_client.open_order_quote_volume_sum",
                                "points": [[self.hummingbot_app.clock.current_timestamp, avg_volume]],
                                **metric_attributes
                            }
                            open_order_usd_volume_sum_metrics = {
                                "metric": "hummingbot_client.open_order_usd_volume_sum",
                                "points": [[self.hummingbot_app.clock.current_timestamp, usd_avg_volume]],
                                **metric_attributes
                            }
                            self.logger().metric_log(open_order_quote_volume_sum_metrics)
                            self.logger().metric_log(open_order_usd_volume_sum_metrics)
                            self.logger().debug(
                                f"Open metrics logged: {open_order_quote_volume_sum_metrics}"
                            )
                        if namespaces[0] == "order_filled_quote_volume":
                            sum_volume = float(sum([value[1] for value in value_list]))
                            usd_sum_volume = self.exchange_converter.exchange_rate.get(quote_token, 1) * sum_volume
                            metric_attributes = {
                                "type": "gauge",
                                "tags": [f"symbol:{trading_pair}",
                                         f"market:{market_name}",
                                         f"order_side:{namespaces[3]}",
                                         f"order_type:{namespaces[4]}"]
                            }
                            order_filled_quote_volume_metrics = {
                                "metric": "hummingbot_client.order_filled_quote_volume",
                                "points": [[self.hummingbot_app.clock.current_timestamp, sum_volume]],
                                **metric_attributes
                            }
                            order_filled_usd_volume_metrics = {
                                "metric": "hummingbot_client.order_filled_usd_volume",
                                "points": [[self.hummingbot_app.clock.current_timestamp, usd_sum_volume]],
                                **metric_attributes
                            }
                            self.logger().metric_log(order_filled_quote_volume_metrics)
                            self.logger().metric_log(order_filled_usd_volume_metrics)
                            self.logger().debug(
                                f"Filled metrics logged: {order_filled_quote_volume_metrics}"
                            )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(f"Error getting logging report.", exc_info=True)

            await asyncio.sleep(self.log_report_interval)

    async def get_open_order_stats(self):
        while True:
            try:
                if not (self.hummingbot_app.strategy and hasattr(self.hummingbot_app.strategy, "active_maker_orders")):
                    await asyncio.sleep(5.0)
                    continue

                _open_orders = defaultdict(list)

                for maker_market, order in self.hummingbot_app.strategy.active_maker_orders:
                    key = f"{maker_market.name}.{order.symbol}"
                    _open_orders[key].append(order.price * order.quantity)
                for market_name, quote_volumes in _open_orders.items():
                    metric_name = f"open_order_quote_volume_sum.{market_name}"
                    metric_value = (self.hummingbot_app.clock.current_timestamp, sum(quote_volumes))
                    self.stats[metric_name].append(metric_value)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(f"Error getting open orders.", exc_info=True)

            await asyncio.sleep(self.report_aggregation_interval)

    async def get_event(self):
        while True:
            try:
                event = await REPORT_EVENT_QUEUE.get()
                self.receive_event(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(f"Error processing events. {event}", exc_info=True)

    def start(self):
        self.stop()
        self.get_open_order_stats_task = safe_ensure_future(self.get_open_order_stats())
        self.get_event_task = safe_ensure_future(self.get_event())
        self.log_report_task = safe_ensure_future(self.log_report())

    def stop(self):
        if self.log_report_task:
            self.log_report_task.cancel()
        if self.get_open_order_stats_task:
            self.get_open_order_stats_task.cancel()
        if self.get_event_task:
            self.get_event_task.cancel()
